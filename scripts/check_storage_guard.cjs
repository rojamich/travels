#!/usr/bin/env node
/*
 * check_storage_guard.cjs — the safety net must not fill the disk it lives on
 * ===========================================================================
 * WHY THIS EXISTS
 *     On 2026-10-01 she could not log in:
 *
 *       Failed to execute setItem on Storage:
 *       Setting the value of gotrue.user exceeded the quota.
 *
 *     Her password was fine. localStorage was full of the editor autosave
 *     history — thirty complete copies of every post she had touched in a
 *     fortnight — so gotrue had nowhere to put the session and there was no
 *     way into the editor at all. The cure had become the disease.
 *
 * WHAT IT CHECKS
 *     - that eviction takes space from the posts she is NOT working on
 *       before the one she is, which is the opposite of what the old code did
 *     - that every post keeps something, and the current one keeps depth
 *     - that the newest version of anything is never the one thrown away
 *     - that nothing outside the safety net is ever touched, gotrue least
 *       of all
 *     - that a full disk is told apart from a wrong password, so a real
 *       login failure is not met with silent deletion
 *     - that storage refusing to answer at all (private mode) breaks nothing
 *
 *     Run against assets/js/storage-guard.js as it is on disk.
 *
 * USAGE
 *     node scripts/check_storage_guard.cjs
 *
 * Exit codes: 0 = every check passed, 1 = something is wrong.
 */
const fs = require("node:fs");
const assert = require("node:assert");

const SRC = fs.readFileSync(process.argv[2] || require("path").join(__dirname, "..", "assets", "js", "storage-guard.js"), "utf8");

function store(obj, cap) {
  const data = Object.assign({}, obj);
  const used = () => Object.keys(data).reduce((n, k) => n + k.length + data[k].length, 0);
  const api = {
    getItem: (k) => (k in data ? data[k] : null),
    removeItem: (k) => { delete data[k]; },
    setItem: (k, v) => {
      v = String(v);
      const after = used() - (k in data ? k.length + data[k].length : 0) + k.length + v.length;
      if (cap && after > cap) {
        const e = new Error("Setting the value of '" + k + "' exceeded the quota.");
        e.name = "QuotaExceededError";
        throw e;
      }
      data[k] = v;
    }
  };
  // Object.keys(localStorage) must see only the data keys.
  const proxy = new Proxy(api, {
    ownKeys: () => Object.keys(data),
    getOwnPropertyDescriptor: () => ({ enumerable: true, configurable: true })
  });
  return { proxy, data, used };
}

function load(st) {
  const w = { localStorage: st.proxy, console: { log() {}, warn() {}, error() {} } };
  new Function("window", "console", SRC)(w, w.console);
  return w.__STORAGE_GUARD;
}

const ver = (ts, chars) => ({ ts, fields: [{ label: "Body", value: "x".repeat(chars) }] });
const hist = (n, base, chars) =>
  JSON.stringify(Array.from({ length: n }, (_, i) => ver(base + i * 1000, chars)));

// ------------------------------------------------------------------ 1
{
  const st = store({
    "editor-form:posts:new": hist(30, 1_000_000, 30000),
    "editor-form:posts:older": hist(30, 500_000, 30000),
    "editor-snapshot:editor-0": "y".repeat(100000),
    "gotrue.user": "{}"
  });
  const g = load(st);
  const before = g.usage();
  g.evict("editor-form:posts:new");

  assert.ok(before > g.BUDGET, "started over budget");
  assert.ok(g.usage() <= g.BUDGET, "ends under budget, got " + g.usage());
  assert.ok(!("editor-snapshot:editor-0" in st.data), "the dead store is gone");
  assert.ok("gotrue.user" in st.data, "the session key is never touched");

  const current = JSON.parse(st.data["editor-form:posts:new"]);
  const other = JSON.parse(st.data["editor-form:posts:older"]);
  assert.ok(current.length >= 8, "the post she is in keeps depth: " + current.length);
  assert.ok(other.length >= 2, "others keep something: " + other.length);
  assert.ok(current.length > other.length, "and she keeps more than they do");
  // Newest must survive; oldest are the ones to go.
  assert.equal(current[current.length - 1].ts, 1_000_000 + 29000, "newest version kept");
  console.log("ok  1  evicts across posts, protects the one she is in" +
              "  (current " + current.length + ", other " + other.length + ")");
}

// ------------------------------------------------------------------ 2
{
  const st = store({
    "editor-form:posts:a": hist(30, 1000, 30000),
    "editor-form:posts:b": hist(30, 2000, 30000),
    "gotrue.user": "{}"
  });
  const g = load(st);
  const freed = g.freeSpaceNow();
  assert.ok(freed > 1_000_000, "frees over a megabyte in the emergency");
  for (const k of ["editor-form:posts:a", "editor-form:posts:b"]) {
    assert.ok(JSON.parse(st.data[k]).length >= 1, k + " keeps its newest");
  }
  assert.ok("gotrue.user" in st.data);
  console.log("ok  2  emergency frees hard but never to nothing");
}

// ------------------------------------------------------------------ 3
{
  const st = store({ "editor-form:posts:junk": "{not json", "gotrue.user": "{}" });
  const g = load(st);
  g.evict(null);
  assert.ok(!("editor-form:posts:junk" in st.data), "unreadable history is dropped");
  assert.ok("gotrue.user" in st.data);
  console.log("ok  3  an unreadable history is not left to rot");
}

// ------------------------------------------------------------------ 4
{
  const st = store({ "gotrue.user": "{}", "upkeep-set-aside": "{}" });
  const g = load(st);
  assert.equal(g.evict(null), 0, "nothing of ours, nothing to free");
  assert.deepEqual(Object.keys(st.data).sort(), ["gotrue.user", "upkeep-set-aside"]);
  console.log("ok  4  leaves a tidy store completely alone");
}

// ------------------------------------------------------------------ 5
{
  const g = load(store({}));
  const q = new Error("Setting the value of 'gotrue.user' exceeded the quota.");
  q.name = "QuotaExceededError";
  assert.equal(g.isQuotaError(q), true, "Chrome's wording");
  assert.equal(g.isQuotaError({ name: "NS_ERROR_DOM_QUOTA_REACHED" }), true, "Firefox's");
  assert.equal(g.isQuotaError(new Error("Invalid email or password")), false, "a real login failure");
  assert.equal(g.isQuotaError(new Error("Failed to fetch")), false, "a network blip");
  assert.equal(g.isQuotaError(null), false);
  console.log("ok  5  tells a full disk from a wrong password");
}

// ------------------------------------------------------------------ 6
// localStorage throwing on every access (private mode) must not break it.
{
  const hostile = new Proxy({}, {
    get() { throw new Error("denied"); },
    ownKeys() { throw new Error("denied"); }
  });
  const w = { localStorage: hostile, console: { log() {}, warn() {}, error() {} } };
  new Function("window", "console", SRC)(w, w.console);
  const g = w.__STORAGE_GUARD;
  assert.equal(g.usage(), 0);
  assert.equal(g.evict(null), 0);
  assert.equal(g.freeSpaceNow(), 0);
  console.log("ok  6  survives storage that refuses to answer");
}

console.log("\nstorage guard: all good");

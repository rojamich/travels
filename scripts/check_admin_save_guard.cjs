#!/usr/bin/env node
/*
 * check_admin_save_guard.cjs — the editor tells the truth about GitHub
 * ===========================================================================
 * WHY THIS EXISTS
 *     On 2026-09-03 a finished post was published as an older draft. The
 *     save had been refused, so the branch still held the previous version;
 *     Publish merged that branch and reported success, because merging is
 *     all Publish does. Nothing in the editor was in a position to notice.
 *
 *     admin/index.html now watches what GitHub actually receives and
 *     refuses to publish while the screen is ahead of GitHub. Those are
 *     decisions made in a browser at the worst possible moment, so they are
 *     tested here rather than found out the hard way.
 *
 * WHAT IT CHECKS
 *     - which requests count as a save and which are ignored
 *     - which failures are real and which are Decap tidying up after itself
 *     - whether the screen is ahead of GitHub, including the case where two
 *       writes land in the same millisecond
 *     - which buttons the publish guard stands in front of
 *     - whether a save that died on a READ is still noticed, since no
 *       write failed and there was nothing for the watcher to catch
 *     - which of Decap's local backups get dropped, since the shared
 *       new-post slot must go and the per-post ones must not
 *     - that the version RECOVERY_LIST names is the version RECOVERY_FORM
 *       hands back, which is the whole of getting a lost draft home
 *
 *     The functions are pulled out of admin/index.html as it is on disk, so
 *     this cannot drift away from what actually ships.
 *
 *     .cjs, not .js: package.json says "type": "module", and this uses
 *     require() to read the page off disk.
 *
 * USAGE
 *     node scripts/check_admin_save_guard.cjs
 *
 * Exit codes: 0 = every check passed, 1 = something is wrong.
 */
const fs = require("fs");
const path = require("path");

const target = process.argv[2] ||
  path.join(__dirname, "..", "admin", "index.html");
const HTML = fs.readFileSync(target, "utf8");

let pass = 0, fail = 0;
function check(name, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "ok  " : "FAIL"}  ${name}` +
              (ok ? "" : `\n          got ${JSON.stringify(got)}, want ${JSON.stringify(want)}`));
  ok ? pass++ : fail++;
}

// ---------------------------------------------------------------- watcher
const watcherSrc = HTML.match(/<script>([\s\S]*?)<\/script>/)[1];
const win = {};
const calls = [];
win.fetch = function (url, init) {
  calls.push([url, init && init.method]);
  const r = init && init.__reject;
  if (r) return Promise.reject(new Error("Failed to fetch"));
  return Promise.resolve({ ok: init.__status < 400, status: init.__status,
                           statusText: init.__text || "" });
};
global.window = win;
new Function("window", "console", watcherSrc)(win, console);
const W = win.__SAVE_WATCH;

async function hit(url, method, status, opts = {}) {
  try { await win.fetch(url, Object.assign({ method, __status: status }, opts)); }
  catch (e) {}
}

(async () => {
  console.log("\nsave watcher — what it counts and what it ignores");

  check("nothing observed yet", [W.seenAny, W.lastOkMs, W.lastFailMs], [false, 0, 0]);

  // A read is not a save. Decap makes hundreds of these.
  await hit("https://api.github.com/repos/rojamich/travels/contents/_posts/a.md", "GET", 200);
  check("a GET is not a write", W.seenAny, false);

  // Neither is traffic to anywhere else (Cloudinary, unpkg).
  await hit("https://api.cloudinary.com/v1_1/x/upload", "POST", 200);
  check("a non-GitHub POST is ignored", W.seenAny, false);
  // Nor the old Git Gateway address, which nothing writes to any more.
  await hit("https://site/.netlify/git/github/git/blobs", "POST", 500);
  check("the retired Git Gateway address is ignored", W.seenAny, false);

  // A real save.
  await hit("https://api.github.com/repos/rojamich/travels/git/blobs", "POST", 201);
  check("a successful write is recorded", [W.seenAny, W.lastOkMs > 0], [true, true]);
  check("healthy after a good write", W.healthy(), true);

  // Routine tidy-up that must not cry wolf.
  const okBefore = W.lastOkMs;
  await hit("https://api.github.com/repos/rojamich/travels/git/refs/heads/cms%2Fx", "DELETE", 404);
  check("a 404 on cleanup is not an alarm", [W.lastFailMs, W.lastOkMs], [0, okBefore]);
  await hit("https://api.github.com/repos/rojamich/travels/git/refs", "POST", 422);
  check("a 422 already-exists is not an alarm", W.lastFailMs, 0);

  // The failure that lost her post.
  let heard = null;
  W.onEvent((kind, w) => { heard = kind + ":" + w.lastFailText; });
  await hit("https://api.github.com/repos/rojamich/travels/git/commits", "POST", 401, { __text: "Unauthorized" });
  check("a 401 is a lost save", W.lastFailMs > 0, true);
  check("and it is announced", heard, "fail:401 Unauthorized");
  check("not healthy once a write was refused", W.healthy(), false);

  // A save that never left the machine at all.
  W.lastFailMs = 0; W.lastFailSeq = 0; heard = null;
  await hit("https://api.github.com/repos/rojamich/travels/git/trees", "POST", 200, { __reject: true });
  check("a dropped connection is a lost save", [W.lastFailMs > 0, heard.startsWith("fail:")], [true, true]);

  // Recovery.
  await hit("https://api.github.com/repos/rojamich/travels/git/refs/heads/main", "PATCH", 200);
  check("healthy again after a good write", W.healthy(), true);
  check("every call still reached the real fetch", calls.length, 9);

  // ------------------------------------------------------------- saveState
  console.log("\nsaveState — is the screen ahead of GitHub?");

  const grab = (name, indent) => {
    const i = HTML.indexOf((indent || "        ") + "function " + name + "(");
    if (i < 0) throw new Error("cannot find " + name);
    let depth = 0, j = HTML.indexOf("{", i);
    for (let k = j; k < HTML.length; k++) {
      if (HTML[k] === "{") depth++;
      else if (HTML[k] === "}" && --depth === 0) return HTML.slice(i, k + 1);
    }
    throw new Error("unbalanced " + name);
  };

  const make = (watch, lastEditMs) => new Function("window", "lastEditMs",
    grab("saveState") + "\n return saveState();")(
      { __SAVE_WATCH: watch }, lastEditMs);

  const T = 1000000;
  check("no writes seen at all -> cannot tell, stay quiet",
        make({ seenAny: false, lastOkMs: 0, lastFailMs: 0, lastOkSeq: 0, lastFailSeq: 0 }, T), null);
  check("no __SAVE_WATCH at all -> cannot tell",
        new Function("window", "lastEditMs", grab("saveState") + "\n return saveState();")({}, T),
        null);
  check("typed since the last good save -> unsaved",
        make({ seenAny: true, lastOkMs: T - 60000, lastFailMs: 0, lastOkSeq: 1, lastFailSeq: 0 }, T), "unsaved");
  check("saved after the last keystroke -> saved",
        make({ seenAny: true, lastOkMs: T + 2000, lastFailMs: 0, lastOkSeq: 1, lastFailSeq: 0 }, T), "saved");
  check("opened a post and typed nothing -> saved",
        make({ seenAny: true, lastOkMs: T, lastFailMs: 0, lastOkSeq: 1, lastFailSeq: 0 }, 0), "saved");
  check("a refused write outranks everything, even at the same millisecond -> failed",
        make({ seenAny: true, lastOkMs: T, lastFailMs: T, lastOkSeq: 1, lastFailSeq: 2 }, T - 5000), "failed");
  check("a failure since fixed, same millisecond -> saved",
        make({ seenAny: true, lastOkMs: T, lastFailMs: T, lastOkSeq: 3, lastFailSeq: 2 }, T - 5000), "saved");

  // --------------------------------------------------- publish button match
  console.log("\nlooksLikeShipButton — what the guard stands in front of");
  const ship = new Function("return " + grab("looksLikeShipButton"))();
  const el = (text) => ({ nodeType: 1, textContent: text });
  [["Publish", true], ["Publish now", true], ["Publish and create new", true],
   ["Set status: Ready", true], ["Set status", true],
   ["Save", false], ["Delete unpublished entry", false], ["New Post", false],
   ["Writing in posts collection", false], ["", false]].forEach(([text, want]) => {
    check(`"${text}" ${want ? "is" : "is not"} blocked`, ship(el(text)), want);
  });
  check("a whole toolbar of text is not a button", ship(el("Publish " + "x".repeat(80))), false);
  check("a text node is not a button", ship({ nodeType: 3, textContent: "Publish" }), false);

    // ------------------------------------- a save that quietly went nowhere
  // Her 2026-09-02 log has the save dying on a READ -- the pull-request
  // lookup Decap does before it writes anything -- so the save never got as
  // far as a write and there was no failed write to notice. This watches
  // the outcome instead: Save was pressed, and GitHub still has nothing.
  console.log("\nwatchThisSaveLands — Save was pressed and nothing arrived");

  function saveWatch(opts) {
    const log = [];
    let fired = null;
    const fakeSetTimeout = (fn, ms) => { fired = ms; fn(); };
    new Function("window", "setTimeout", "console", "saveState", "showSaveFailBar",
                 "Date",
      "var SAVE_GRACE_MS = 30 * 1000;\n" +
      grab("watchThisSaveLands") + "\n" +
      "watchThisSaveLands();"
    )({ __SAVE_WATCH: opts.watch },
      fakeSetTimeout,
      { warn: (m) => log.push("warn:" + m), log: () => {} },
      () => opts.state,
      (why) => log.push("bar:" + why),
      { now: () => opts.now || 1000 });
    return { log, delay: fired };
  }

  const CLICK = 1000;
  const barred = (r) => r.log.some((l) => l.startsWith("bar:"));

  check("it waits well past any real save",
        saveWatch({ watch: { seenAny: true, lastOkMs: 0 }, state: "saved" }).delay, 30000);

  check("says nothing when no write has ever been seen",
        barred(saveWatch({ watch: { seenAny: false, lastOkMs: 0 }, state: "unsaved" })), false);

  check("says nothing when __SAVE_WATCH is missing entirely",
        barred(saveWatch({ watch: null, state: "unsaved" })), false);

  check("says nothing when a write landed after the click",
        barred(saveWatch({ watch: { seenAny: true, lastOkMs: CLICK + 500 },
                           state: "saved", now: CLICK })), false);

  check("says nothing when there was nothing to save",
        barred(saveWatch({ watch: { seenAny: true, lastOkMs: CLICK - 5000 },
                           state: "saved", now: CLICK })), false);

  check("leaves a refused write to the bar that is already up",
        barred(saveWatch({ watch: { seenAny: true, lastOkMs: CLICK - 5000 },
                           state: "failed", now: CLICK })), false);

  const caught = saveWatch({ watch: { seenAny: true, lastOkMs: CLICK - 5000 },
                             state: "unsaved", now: CLICK });
  check("speaks up when the save simply never arrived", barred(caught), true);
  check("and says so in the bar", caught.log.filter((l) => l.startsWith("bar:")),
        ["bar:it never completed"]);
  check("and leaves a line in the console for you",
        caught.log.some((l) => /nothing has reached GitHub/.test(l)), true);

  // ------------------------------------ Decap's shared new-post backup
  // Decap names a new post's backup after its collection alone, because it
  // has no slug yet -- so every new post shares one slot, and the prompt
  // that offers it compares nothing. It gets emptied at load. The per-post
  // backups name one entry each, work correctly, and must survive that.
  console.log("\nwhich local backups get dropped");

  const isSharedSlot = new Function("return " + grab("isSharedSlot", "      "))();
  [["backup", true],
   ["backup.posts", true],
   ["backup.trips", true],
   ["backup.site-config", true],
   ["backup.posts.2026-03-17-the-one-where-we-fly-north", false],
   ["backup.posts.a.b", false],
   ["backupish", false],
   ["notabackup", false],
   ["", false]].forEach(([key, want]) => {
    check(`${JSON.stringify(key)} ${want ? "is dropped" : "is kept"}`,
          isSharedSlot(key), want);
  });

  // ------------------------------------------------- clearing up the old
  // Nothing writes the second snapshot store any more, so it ages out and
  // goes. It ages out rather than being deleted on sight on purpose: what
  // is in it on the first load after the upgrade may be the only copy of a
  // draft somebody is halfway through recovering.
  console.log("\ncleanOld — what it sweeps up");

  function storage(obj) {
    const o = Object.assign({}, obj);
    const def = (n, f) => Object.defineProperty(o, n, { value: f, enumerable: false });
    def("getItem", (k) => (k in o ? o[k] : null));
    def("setItem", (k, v) => { o[k] = String(v); });
    def("removeItem", (k) => { delete o[k]; });
    return o;
  }

  const DAY = 24 * 60 * 60 * 1000;
  const fresh = JSON.stringify([{ ts: Date.now() - DAY, fields: [] }]);
  const stale = JSON.stringify([{ ts: Date.now() - 30 * DAY, fields: [] }]);
  const store = storage({
    "editor-history:editor-0": fresh,          // the upgrade must not eat this
    "editor-snapshot:editor-0": stale,
    "editor-history:editor-9": stale,
    "editor-form:posts:new": fresh,
    "editor-form:posts:old-trip": stale,
    "editor-form:posts:broken": "{not json",
    "gotrue.user": "hers",
    "upkeep-set-aside": "{}"
  });

  // Lifted off the page rather than retyped, so that changing what counts
  // as dead, or how old is too old, changes this test along with it.
  const sweepDecls = HTML.match(
    /var MAX_AGE_MS\s*=[\s\S]*?var DEAD_PREFIXES\s*=[^;]*;/)[0];

  new Function("localStorage", "FORM_PREFIX", "Date",
    sweepDecls + "\n" + grab("isOurs") + "\n" + grab("cleanOld") + "\ncleanOld();"
  )(store, "editor-form:", Date);

  const left = Object.keys(store).sort();
  check("a draft still sitting in the deleted store is NOT eaten by the upgrade",
        left.includes("editor-history:editor-0"), true);
  check("but an old one from it is swept up",
        left.filter((k) => k === "editor-snapshot:editor-0" ||
                           k === "editor-history:editor-9"), []);
  check("a recent draft history is kept", left.includes("editor-form:posts:new"), true);
  check("one from a month ago is not", left.includes("editor-form:posts:old-trip"), false);
  check("an unreadable one is dropped rather than left to rot",
        left.includes("editor-form:posts:broken"), false);
  check("and nothing else is touched",
        left.filter((k) => !k.startsWith("editor-")).sort(),
        ["gotrue.user", "upkeep-set-aside"]);

  // ------------------------------------------ finding the right version
  // What was missing when a draft was replaced by an older one: the newest
  // version is the damage, so the question is which of the kept ones she
  // actually wrote. RECOVERY_LIST names them by size; the number it prints
  // has to be the number RECOVERY_FORM answers to, or it is worse than
  // useless at exactly the wrong moment.
  console.log("\nRECOVERY_LIST and RECOVERY_FORM agree on which is which");

  function grabAssigned(name) {
    const i = HTML.indexOf("window." + name + " = function");
    if (i < 0) throw new Error("cannot find window." + name);
    let depth = 0;
    for (let k = HTML.indexOf("{", i); k < HTML.length; k++) {
      if (HTML[k] === "{") depth++;
      else if (HTML[k] === "}" && --depth === 0) return HTML.slice(i, k + 1) + ";";
    }
    throw new Error("unbalanced " + name);
  }

  const versions = [
    { ts: Date.parse("2026-09-19T10:00:00"), fields: [{ label: "Body", value: "x".repeat(300) }] },
    { ts: Date.parse("2026-09-19T11:30:00"), fields: [{ label: "Body", value: "y".repeat(7400) }] },
    { ts: Date.parse("2026-09-19T11:45:00"), fields: [{ label: "Body", value: "z".repeat(100) }] }
  ];
  const lines = [];
  const recoveryWin = {};
  new Function("localStorage", "console", "window", "FORM_PREFIX", "Date",
    grab("formHistories") + "\n" + grabAssigned("RECOVERY_LIST") + "\n" +
    grabAssigned("RECOVERY_FORM")
  )(storage({ "editor-form:posts:new": JSON.stringify(versions) }),
    { log: (m) => lines.push(String(m)) }, recoveryWin, "editor-form:", Date);

  recoveryWin.RECOVERY_LIST();
  const big = lines.find((l) => l.includes("7400 chars"));
  check("the version she wrote is listed by its size", !!big, true);

  const idx = Number(big.match(/RECOVERY_FORM\((\d+)\)/)[1]);
  check("and it is not the newest one", idx > 0, true);

  lines.length = 0;
  recoveryWin.RECOVERY_FORM(idx);
  check("asking for that number gives back that version",
        lines.some((l) => l.length === 7400 && l[0] === "y"), true);

  // ------------------------------------------ handing a version back
  // 2026-10-07: every word of her post was in the backup, as 19,000
  // characters of which most were the gallery forms' labels, and none of
  // the photos. What she is handed has to be her post, not the editor's
  // furniture -- and when Decap's own copy was kept, exactly that copy.
  console.log("\na kept version comes back as her post");

  const tidy = new Function("return " + grab("tidyScreenText"))();
  const HINTS = "Click here, then upload or pick a photo. Repeat 'Add' to add more.\n\n" +
    "FOCAL X (0–100) (OPTIONAL)\n\nOnly matters if the photo is being cropped in its tile.\n\n" +
    "FOCAL Y (0–100) (OPTIONAL)\n\n0 = keep the top of the photo.\n\n";
  const galleryTail = "Add as many photos as you want — they'll render in a grid.\n\n" +
    "CAPTION (OPTIONAL) (OPTIONAL)\n\nShown below the gallery in italic.\n\n﻿\n\n";
  const screen =
    "We walked to the reserve.\n\n" +
    "📷 PHOTO GALLERY\nPHOTOS\n2 photos\nAdd photos\n" +
    "IMAGE\nChoose different image\nReplace with URL\nRemove image\n\n" + HINTS +
    "IMAGE\nChoose different image\nReplace with URL\nRemove image\n\n" + HINTS + galleryTail +
    "Then a single photo.\n\n" +
    "IMAGE\nIMAGE\nChoose different image\nReplace with URL\nRemove image\nALT TEXT\nTITLE\n﻿\n\n" +
    "And a video.\n\n" +
    "🎬 YOUTUBE VIDEO\nYOUTUBE URL\n\nPaste the YouTube URL from your browser. Any format works " +
    "(youtube.com/watch?v=..., youtu.be/..., or just the video ID).\n\n﻿\n\n" +
    "📷 PHOTO GALLERY\nPHOTOS\n1 photos\nAdd photos\nhttps://res.cloudinary.com/x/image/upload/a.png\n\n" +
    galleryTail + "The end.";
  const tidied = tidy(screen);
  check("her sentences all survive",
        ["We walked to the reserve.", "Then a single photo.", "And a video.", "The end."]
          .every((s) => tidied.includes(s)), true);
  check("none of the gallery form does",
        /FOCAL|Choose different image|CAPTION|Add photos|﻿/.test(tidied), false);
  check("each gallery becomes one line saying how many photos",
        (tidied.match(/👉 \[PHOTO GALLERY, 2 photos — re-add them\]/g) || []).length, 1);
  check("a single image and a video are marked too",
        [/👉 \[PHOTO — re-add it\]/.test(tidied), /👉 \[YOUTUBE VIDEO/.test(tidied)], [true, true]);
  check("a photo link the screen did show is kept",
        tidied.includes("👉 [PHOTO GALLERY, 1 photos: https://res.cloudinary.com/x/image/upload/a.png]"), true);

  const asFile = new Function("FORM_PREFIX", "tidyScreenText",
    grab("versionBody") + "\n" + grab("versionTitle") + "\n" + grab("versionAsFile") +
    "\nreturn { versionBody: versionBody, versionAsFile: versionAsFile };"
  )("editor-form:", tidy);
  const ts = Date.parse("2026-10-07T14:30:05");
  const exact = {
    ts, fields: [{ label: "Title", value: "San Telmo" }, { label: "Body", value: screen }],
    data: { title: "San Telmo: the market", date: "2026-10-04", trip: "cafes-tango-time",
            gallery: ["https://res.cloudinary.com/x/a.png"],
            body: "Intro.\n\n{% gallery_block %5B%5D %}\n\nThe end." }
  };
  check("Decap's own copy of the body wins when it was kept",
        asFile.versionBody(exact), { text: exact.data.body, exact: true });
  const f = asFile.versionAsFile(exact, "editor-form:posts:new");
  check("and downloads as the post file itself, front matter and all",
        f.text.split("\n").slice(0, 6),
        ["---", 'title: "San Telmo: the market"', 'date: "2026-10-04"',
         'trip: "cafes-tango-time"', 'gallery: ["https://res.cloudinary.com/x/a.png"]', "---"]);
  check("with the body after it, untouched", f.text.endsWith(exact.data.body + "\n"), true);
  check("named after the post and the minute it was kept",
        f.name, "san-telmo-the-market-2026-10-07-1430.md");

  const screenOnly = { ts, fields: exact.fields };
  check("without it, the screen text is tidied rather than handed back raw",
        asFile.versionBody(screenOnly).exact === false &&
        asFile.versionBody(screenOnly).text === tidied, true);
  const t = asFile.versionAsFile(screenOnly, "editor-form:posts:new");
  check("and the file says plainly what is missing",
        [t.name.endsWith(".txt"), /not in this copy/.test(t.text), t.text.includes("Title: San Telmo")],
        [true, true, true]);

  // ------------------------------------------ which entry Decap is holding
  // Moving between posts, Decap's store can still hold the last one for a
  // moment. Filing one post's words under another's name is the 2026-09-19
  // disaster again, so the data is only taken when it is the entry the URL
  // names.
  console.log("\nDecap's copy is only taken for the post she is in");
  const imm = (obj) => ({ get: (k) => obj[k], toJS: () => obj });
  function entryFor(hash, entry) {
    const store = { getState: () => ({ entryDraft: imm({ entry: entry && imm(entry) }) }) };
    return new Function("location", "findDecapStore",
      grab("entryData") + "\nreturn entryData();")({ hash }, () => store);
  }
  const body = imm({ title: "A", body: "words" });
  check("a new post, while a new post is open",
        entryFor("#/collections/posts/new", { collection: "posts", newRecord: true, data: body }),
        { title: "A", body: "words" });
  check("an existing post, by its slug — even an emoji one",
        !!entryFor("#/collections/posts/entries/2024-02-07-surf-%F0%9F%8F%84",
                   { collection: "posts", slug: "2024-02-07-surf-🏄", data: body }), true);
  check("not the post she just left",
        entryFor("#/collections/posts/entries/b", { collection: "posts", slug: "a", data: body }), null);
  check("not a saved post while the URL says new",
        entryFor("#/collections/posts/new", { collection: "posts", slug: "a", newRecord: false, data: body }), null);
  check("not another collection's entry",
        entryFor("#/collections/trips/entries/a", { collection: "posts", slug: "a", data: body }), null);
  check("and nothing at all when there is no store",
        new Function("location", "findDecapStore", grab("entryData") + "\nreturn entryData();")(
          { hash: "#/collections/posts/new" }, () => null), null);

  // ------------------------------------------ putting a version back
  // The one thing in the recovery panel that writes to the editor. It must
  // only ever load a version into the post it came from, keep what was on
  // screen first, and say so when Decap did not take it.
  console.log("\nPut back only loads a version into its own post");
  function putBack({ here, version, key, decapObeys = true }) {
    const log = [];
    let current = { title: "on screen now", body: "newer words" };
    const store = {
      getState: () => ({ entryDraft: { get: () => ({ toJS: () =>
        ({ collection: "posts", slug: "a", path: "_posts/a.md", data: current }) }) } }),
      dispatch: (a) => {
        log.push(a.type);
        if (a.type === "DRAFT_LOCAL_BACKUP_RETRIEVED") log.push(a.payload.entry.path);
        if (decapObeys && a.type === "DRAFT_CREATE_FROM_LOCAL_BACKUP") current = version.data;
      }
    };
    const restore = new Function("FORM_PREFIX", "formKey", "entryData", "findDecapStore",
      "snapshotForm", "console",
      grab("canRestoreHere") + "\n" + grab("restoreVersion") + "\nreturn restoreVersion;"
    )("editor-form:", () => here, () => (here ? current : null), () => store,
      (why) => log.push("snapshot:" + why), { warn() {} });
    return { ok: restore(version, key), log };
  }
  const old = { ts: 1, data: { title: "the one she wrote", body: "all of it" } };
  const good = putBack({ here: "posts:a", version: old, key: "editor-form:posts:a" });
  check("into the post it came from: what's on screen is kept first, then Decap loads it",
        good, { ok: true, log: ["snapshot:before-restore", "DRAFT_LOCAL_BACKUP_RETRIEVED",
                                "_posts/a.md", "DRAFT_CREATE_FROM_LOCAL_BACKUP"] });
  check("never into a different post",
        putBack({ here: "posts:b", version: old, key: "editor-form:posts:a" }), { ok: false, log: [] });
  check("never from the list page, with no post open",
        putBack({ here: null, version: old, key: "editor-form:posts:a" }), { ok: false, log: [] });
  check("never a text-only version, which has no fields to load",
        putBack({ here: "posts:a", version: { ts: 1, fields: [] }, key: "editor-form:posts:a" }),
        { ok: false, log: [] });
  check("and if Decap ignores it, it says it didn't work",
        putBack({ here: "posts:a", version: old, key: "editor-form:posts:a", decapObeys: false }).ok, false);

  // ------------------------------------------ the names she remembers
  check("RECOVERY_HISTORY and RECOVERY_COPY, the names the doc taught, still exist",
        [/window\.RECOVERY_HISTORY = function/.test(HTML), /window\.RECOVERY_COPY = function/.test(HTML)],
        [true, true]);

console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();

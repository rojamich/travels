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
 *     admin/index.html now watches what Git Gateway actually does and
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
 *     - whether a session gotrue quietly cleared is noticed at once
 *     - whether a dropped connection is told apart from a real logout,
 *       so a wifi blip puts the session back instead of ending it
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
  await hit("https://site/.netlify/git/github/contents/_posts/a.md", "GET", 200);
  check("a GET is not a write", W.seenAny, false);

  // Neither is traffic to anywhere else (Cloudinary, Identity, unpkg).
  await hit("https://api.cloudinary.com/v1_1/x/upload", "POST", 200);
  check("a non-GitHub POST is ignored", W.seenAny, false);

  // A real save.
  await hit("https://site/.netlify/git/github/git/blobs", "POST", 201);
  check("a successful write is recorded", [W.seenAny, W.lastOkMs > 0], [true, true]);
  check("healthy after a good write", W.healthy(), true);

  // Routine tidy-up that must not cry wolf.
  const okBefore = W.lastOkMs;
  await hit("https://site/.netlify/git/github/git/refs/heads/cms%2Fx", "DELETE", 404);
  check("a 404 on cleanup is not an alarm", [W.lastFailMs, W.lastOkMs], [0, okBefore]);
  await hit("https://site/.netlify/git/github/git/refs", "POST", 422);
  check("a 422 already-exists is not an alarm", W.lastFailMs, 0);

  // The failure that lost her post.
  let heard = null;
  W.onEvent((kind, w) => { heard = kind + ":" + w.lastFailText; });
  await hit("https://site/.netlify/git/github/git/commits", "POST", 401, { __text: "Unauthorized" });
  check("a 401 is a lost save", W.lastFailMs > 0, true);
  check("and it is announced", heard, "fail:401 Unauthorized");
  check("not healthy once a write was refused", W.healthy(), false);

  // A save that never left the machine at all.
  W.lastFailMs = 0; W.lastFailSeq = 0; heard = null;
  await hit("https://site/.netlify/git/github/git/trees", "POST", 200, { __reject: true });
  check("a dropped connection is a lost save", [W.lastFailMs > 0, heard.startsWith("fail:")], [true, true]);

  // Recovery.
  await hit("https://site/.netlify/git/github/git/refs/heads/main", "PATCH", 200);
  check("healthy again after a good write", W.healthy(), true);
  check("every call still reached the real fetch", calls.length, 8);

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

    // ------------------------------------------------- a session gotrue cleared
  // gotrue-js calls clearSession() on ANY failed refresh, including a
  // network one, so "logged out" arrives with no warning and no auth-shaped
  // error message. These check that the page looks at the session itself
  // rather than at how the failure was worded.
  console.log("\nsessionIsGone / handleLostSession — the silent logout");

  const sessionSrc =
    "var everHadUser = false;\n" +
    "var dismissedUntilMs = arguments[5] || 0;\n" +
    grab("currentUserOrNull", "      ") + "\n" +
    grab("sessionIsGone", "      ") + "\n" +
    grab("handleLostSession", "      ") + "\n";

  function session(opts) {
    const log = [];
    const win = {
      netlifyIdentity: { currentUser: opts.currentUser },
      __FORCE_SNAPSHOT: (why) => log.push("snapshot:" + why)
    };
    // netlifyIdentity is passed separately because the page reads it as a
    // bare global as well as through window -- the same binding in a
    // browser, two different things inside new Function().
    const api = new Function(
      "window", "netlifyIdentity", "sessionIsDead", "safeToShowDeadModal",
      "showDeadSessionModal",
      sessionSrc +
      "return { gone: sessionIsGone, handle: handleLostSession," +
      "         seen: function () { return everHadUser; } };"
    )(win, win.netlifyIdentity, !!opts.alreadyDead,
      () => opts.pastStartup !== false,
      (why) => log.push("modal:" + why),
      opts.dismissedUntilMs || 0);
    return { api, log };
  }

  const user = () => ({ token: {} });
  const none = () => null;

  let s = session({ currentUser: none });
  check("no session at startup is not a lost session", s.api.gone(), false);

  s = session({ currentUser: user });
  check("a live session is not lost", s.api.gone(), false);
  check("and it is remembered", s.api.seen(), true);

  // The one that matters: there was a user, and now there is not.
  let live = true;
  s = session({ currentUser: () => (live ? { token: {} } : null) });
  s.api.gone();                       // first look: signed in
  live = false;                       // gotrue clears the session
  check("a session that vanished is lost", s.api.gone(), true);

  live = true;
  s = session({ currentUser: () => { if (live) return { token: {} }; throw new Error("boom"); } });
  s.api.gone();
  live = false;
  check("currentUser() throwing counts as gone", s.api.gone(), true);

  // handleLostSession: modal, snapshot, and the guards around them.
  live = true;
  s = session({ currentUser: () => (live ? { token: {} } : null) });
  check("nothing happens while signed in", s.api.handle("test"), false);
  check("and nothing was logged", s.log, []);

  live = false;
  check("a lost session is handled", s.api.handle("refresh-cleared-session:focus"), true);
  check("her work is snapshotted before the modal",
        s.log, ["snapshot:session-lost", "modal:refresh-cleared-session:focus"]);

  live = true;
  s = session({ currentUser: () => (live ? { token: {} } : null), pastStartup: false });
  s.api.gone();
  live = false;
  check("the 90s startup window suppresses it", s.api.handle("startup"), false);
  check("and nothing was logged then either", s.log, []);

  live = true;
  s = session({ currentUser: () => (live ? { token: {} } : null), alreadyDead: true });
  s.api.gone();
  live = false;
  check("no second modal once one is already up", s.api.handle("again"), false);

  // Her log is a run of watchdog / save-click / watchdog: the modal being
  // dismissed and put straight back fifteen seconds later. Dismiss now
  // buys her the quiet it always claimed to.
  live = true;
  s = session({ currentUser: () => (live ? { token: {} } : null),
                dismissedUntilMs: Date.now() + 5 * 60 * 1000 });
  s.api.gone();
  live = false;
  check("a dismissed modal stays dismissed", s.api.handle("watchdog"), false);
  check("and nothing is logged while it is dismissed", s.log, []);

  live = true;
  s = session({ currentUser: () => (live ? { token: {} } : null),
                dismissedUntilMs: Date.now() - 1000 });
  s.api.gone();
  live = false;
  check("once the quiet window lapses it speaks up again",
        s.api.handle("watchdog"), true);

    // ------------------------------------------ a blip must not cost the login
  // gotrue deletes the stored session in its catch, whatever the catch was
  // for. When the cause was the network the refresh token was never spent,
  // so the session is still good and gets put back. When the cause was the
  // login itself, it must not be -- that would paper over a real logout.
  console.log("\nlooksLikeNetwork — the network failed, or the login did?");

  const netCheck = new Function("return " + grab("looksLikeNetwork", "      "))();
  [
    ["Failed to fetch", true, "Chrome, connection dropped"],
    ["NetworkError when attempting to fetch resource.", true, "Firefox"],
    ["Load failed", true, "Safari"],
    ["net::ERR_CONNECTION_CLOSED", true, "what her log showed"],
    ["net::ERR_NETWORK_CHANGED", true, "wifi switched"],
    ["The operation was aborted.", true, "request cancelled"],
    ["invalid_grant", false, "refresh token genuinely rejected"],
    ["401 Unauthorized", false, "server said no"],
    ["403 Forbidden", false, "server said no"],
    ["invalid_token", false, "token genuinely bad"],
    ["Failed to fetch: 401 Unauthorized", false, "auth wins over the wording"],
    ["", false, "nothing to go on"]
  ].forEach(([msg, want, why]) => {
    check(`${want ? "restore" : "do NOT restore"} on "${msg || "(empty)"}" — ${why}`,
          netCheck(msg), want);
  });

  console.log("\nputSessionBack — only when there is a gap to fill");

  function withStorage(initial) {
    const store = Object.assign({}, initial);
    const localStorage = {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; }
    };
    const fn = new Function("localStorage", "currentUserOrNull",
      'var SESSION_KEY = "gotrue.user";\n' +
      grab("storedSession", "      ") + "\n" +
      grab("putSessionBack", "      ") + "\n" +
      "return { stored: storedSession, put: putSessionBack };"
    )(localStorage, () => (store["gotrue.user"] ? { token: {} } : null));
    return { api: fn, store };
  }

  let st = withStorage({ "gotrue.user": '{"token":{"access_token":"abc"}}' });
  const saved = st.api.stored();
  check("the session is read before the refresh", saved, '{"token":{"access_token":"abc"}}');

  // gotrue's catch has just run.
  delete st.store["gotrue.user"];
  check("it goes back after a network failure", st.api.put(saved), true);
  check("and the stored value is byte-identical",
        st.store["gotrue.user"], '{"token":{"access_token":"abc"}}');

  // A live session must never be overwritten by a stale copy.
  st = withStorage({ "gotrue.user": '{"token":{"access_token":"NEW"}}' });
  check("a live session is left alone", st.api.put('{"token":{"access_token":"OLD"}}'), false);
  check("and still holds the new token",
        st.store["gotrue.user"], '{"token":{"access_token":"NEW"}}');

  st = withStorage({});
  check("nothing to restore is not a restore", st.api.put(null), false);
  check("no session before the refresh means nothing to put back", st.api.stored(), null);

  console.log("\nrefreshIsThrottled — which callers may be made to wait");
  const throttled = new Function("return " + grab("refreshIsThrottled", "      "))();
  [["save-click", false], ["save-click-held", false], ["expiry-watch", false],
   ["focus", true], ["visibilitychange", true], ["periodic", true],
   ["", true], [undefined, true]].forEach(([reason, want]) => {
    check(`${JSON.stringify(reason)} ${want ? "waits" : "always goes"}`,
          throttled(reason), want);
  });

  console.log(`\n${pass} passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})();

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
 *     - whether a save that died on a READ is still noticed, since no
 *       write failed and there was nothing for the watcher to catch
 *     - whether a session gotrue quietly cleared is noticed at once
 *     - whether a dropped connection is told apart from a real logout,
 *       so a wifi blip puts the session back instead of ending it
 *     - whether the notes lookup Git Gateway will never answer is answered
 *       in the browser, and nothing else is
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

  // ------------------------------------------------------- notes lookup
  // Git Gateway proxies an allowlist of GitHub's API and /search/ is not on
  // it, so decap-cms-core 3.17's notes lookup 401s every time and publishing
  // prints a red error that means nothing. It is answered in the browser
  // instead, with the truth: there are no notes. If that ever starts going
  // out to the network again, the noise comes back.
  const before = calls.length;
  const notesUrl = "https://site/.netlify/git/github/search/issues" +
    "?q=repo%3A%20label%3Adecap-cms-notes%20%22posts%2Fx%22%20in%3Abody%20state%3Aopen";
  const notes = await win.fetch(notesUrl, { method: "GET" });
  check("the notes lookup never leaves the browser", calls.length, before);
  check("and is answered, not refused", notes.status, 200);
  check("with no notes to close", (await notes.json()).items, []);

  // Only that one endpoint. Everything else Decap reads must still go out,
  // or this stops being a fix and starts being a hole.
  await hit("https://site/.netlify/git/github/contents/_posts/a.md", "GET", 200);
  check("an ordinary read still goes out", calls.length, before + 1);
  await hit("https://site/.netlify/git/github/git/blobs", "POST", 201);
  check("a save still goes out", calls.length, before + 2);

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
                 "retryTheSave", "Date",
      "var SAVE_GRACE_MS = 30 * 1000;\n" +
      grab("watchThisSaveLands") + "\n" +
      "watchThisSaveLands();"
    )({ __SAVE_WATCH: opts.watch },
      fakeSetTimeout,
      { warn: (m) => log.push("warn:" + m), log: () => {} },
      () => opts.state,
      (why) => log.push("bar:" + why),
      (why) => { log.push("retry:" + why); return !!opts.retries; },
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

  check("a save it can rescue is rescued, not reported",
        barred(saveWatch({ watch: { seenAny: true, lastOkMs: CLICK - 5000 },
                           state: "unsaved", now: CLICK, retries: true })), false);

  check("and it is the retry that is reached for first",
        saveWatch({ watch: { seenAny: true, lastOkMs: CLICK - 5000 },
                    state: "unsaved", now: CLICK, retries: true }).log[0],
        "retry:watchdog");

  const caught = saveWatch({ watch: { seenAny: true, lastOkMs: CLICK - 5000 },
                             state: "unsaved", now: CLICK });
  check("speaks up when the save simply never arrived", barred(caught), true);
  check("and says so in the bar", caught.log.filter((l) => l.startsWith("bar:")),
        ["bar:it never completed"]);
  check("and leaves a line in the console for you",
        caught.log.some((l) => /nothing has reached GitHub/.test(l)), true);

    // --------------------------------------------------- saving again
  // A save that died because the session had been cleared is worth one more
  // attempt: nothing of it reached GitHub, her words never left the page,
  // and the refresh token was never spent. Every one of these rules exists
  // to keep that from becoming "press buttons and hope".
  console.log("\nretrying a save the dropped session killed");

  const tokenWasGone = new Function("return " + grab("tokenWasGone"))();
  check("gotrue's own words are the signal",
        tokenWasGone("Gotrue-js: failed getting jwt access token"), true);
  check("a refresh that failed is a different problem", tokenWasGone("Failed to fetch"), false);
  check("so is a rejected login", tokenWasGone("invalid_grant"), false);
  check("and nothing at all is not a signal", tokenWasGone(""), false);
  check("nor is undefined", tokenWasGone(undefined), false);

  const reasonMessage = new Function("return " + grab("reasonMessage"))();
  check("an Error is read for its message",
        reasonMessage(new Error("Gotrue-js: failed getting jwt access token")),
        "Gotrue-js: failed getting jwt access token");
  check("a string is its own message", reasonMessage("boom"), "boom");
  check("Decap's #<Object> is searched too",
        tokenWasGone(reasonMessage({ err: "Gotrue-js: failed getting jwt access token" })), true);
  check("nothing rejected, nothing to read", reasonMessage(null), "");

  const shouldRetry = new Function(
    "var RETRY_WINDOW_MS = 60 * 1000;\nreturn " + grab("shouldRetrySave"))();
  const NOW = 500000;
  const died = { clickedAt: NOW - 2000, isPublish: false, retried: false,
                 lastOkMs: NOW - 90000, sessionBack: true };
  const but = (o) => Object.assign({}, died, o);

  check("a save that died with the session put back is retried",
        shouldRetry(NOW, died), true);
  check("Publish is never pressed again for her", shouldRetry(NOW, but({ isPublish: true })), false);
  check("once is once", shouldRetry(NOW, but({ retried: true })), false);
  check("a save nobody started is not retried", shouldRetry(NOW, but({ clickedAt: 0 })), false);
  check("nor one from two minutes ago",
        shouldRetry(NOW, but({ clickedAt: NOW - 120000 })), false);
  check("a save that actually landed is left alone",
        shouldRetry(NOW, but({ lastOkMs: NOW - 1000 })), false);
  check("and without a session there is nothing to retry with",
        shouldRetry(NOW, but({ sessionBack: false })), false);
  check("no context at all is not a retry", shouldRetry(NOW, null), false);

  // The button it presses. Publish must be unreachable from here however
  // the toolbar is worded, because pressing it is the one thing in this
  // editor that cannot be taken back.
  const findSaveButton = new Function("document", "return " + grab("findSaveButton"))(
    { querySelectorAll: () => [
        { textContent: "Publish" }, { textContent: "Publish now" },
        { textContent: "Set status: Ready" }, { textContent: "Delete unpublished entry" },
        { textContent: " Save " }, { textContent: "Save and publish" }] });
  check("it finds Save", (findSaveButton() || {}).textContent, " Save ");

  const noSave = new Function("document", "return " + grab("findSaveButton"))(
    { querySelectorAll: () => [{ textContent: "Publish" }, { textContent: "Save and publish" }] });
  check("and finds nothing rather than something near enough", noSave(), null);

  // ------------------------------------------- and pressing the button
  // The rules above decide whether to retry. This is the part that actually
  // presses Save in her editor, so it is worth watching it do it.
  console.log("\nretryTheSave — what it actually does");

  function retryRig(opts) {
    const log = [];
    const button = { textContent: "Save", click: () => log.push("CLICKED SAVE") };
    const doc = { querySelectorAll: () => (opts.noButton ? [] : [button]) };
    let restored = false;

    const made = new Function(
      "window", "document", "console", "Date",
      "currentUserOrNull", "signedOutOnPurpose", "putSessionBack", "lastGoodSession",
      "showToast", "tokenSecondsLeft", "refreshNow",
      "safeToShowDeadModal", "showDeadSessionModal", "watchThisSaveLands", "seed",
      "var RETRY_WINDOW_MS = 60 * 1000;\n" +
      "var lastSaveClick = seed;\n" +
      grab("shouldRetrySave") + "\n" +
      grab("findSaveButton") + "\n" +
      grab("reviveSession") + "\n" +
      grab("retryTheSave") + "\n" +
      "return { retry: retryTheSave, click: function () { return lastSaveClick; } };"
    )(
      { __SAVE_WATCH: opts.watch || { lastOkMs: 0 } },
      doc,
      { log: (m) => log.push("log:" + m), warn: (m) => log.push("warn:" + m) },
      { now: () => opts.now },
      () => (opts.alive ? { id: "u" } : null),
      !!opts.signedOut,
      () => { restored = !opts.cannotRestore; return restored; },
      opts.cannotRestore ? null : "{\"a\":1}",
      (t) => log.push("toast:" + t),
      () => (opts.tokenLeft === undefined ? 900 : opts.tokenLeft),
      (why) => { log.push("refresh:" + why); return Promise.resolve(!opts.refreshFails); },
      () => true,
      (why) => log.push("modal:" + why),
      () => log.push("rewatch"),
      opts.seed || { at: opts.now - 3000, isPublish: false, retried: false }
    );
    return { log, made, restored: () => restored };
  }

  const NOW2 = 900000;

  // The whole point: the session was gone, it goes back, Save is pressed.
  {
    const r = retryRig({ now: NOW2, alive: false });
    const took = r.made.retry("token-gone");
    await Promise.resolve(); await Promise.resolve();
    check("it takes the save on", took, true);
    check("it puts the session back", r.restored(), true);
    check("it tells her before doing it",
          r.log.some((l) => l.startsWith("toast:")), true);
    check("and it presses Save", r.log.includes("CLICKED SAVE"), true);
    check("then keeps watching the second attempt too", r.log.includes("rewatch"), true);
  }

  // Twice through the door -- the rejection fires AND the watchdog fires --
  // must still be one press. Two saves of the same post is not a disaster,
  // but it is not something to leave to chance either.
  {
    const r = retryRig({ now: NOW2, alive: false });
    r.made.retry("token-gone");
    const second = r.made.retry("watchdog");
    await Promise.resolve(); await Promise.resolve();
    check("a second caller is turned away", second, false);
    check("and Save is pressed exactly once",
          r.log.filter((l) => l === "CLICKED SAVE").length, 1);
  }

  // A live token that was never the problem: no need to spend a refresh on
  // a network that may still be down.
  {
    const r = retryRig({ now: NOW2, alive: true, tokenLeft: 900 });
    r.made.retry("token-gone");
    await Promise.resolve(); await Promise.resolve();
    check("a healthy token is not renewed for nothing",
          r.log.some((l) => l.startsWith("refresh:")), false);
    check("it just saves", r.log.includes("CLICKED SAVE"), true);
  }

  // Nearly out of time: renew first, then save.
  {
    const r = retryRig({ now: NOW2, alive: true, tokenLeft: 30 });
    r.made.retry("token-gone");
    await Promise.resolve(); await Promise.resolve(); await Promise.resolve();
    check("a token nearly out of time is renewed first",
          r.log.indexOf("refresh:save-retry") < r.log.indexOf("CLICKED SAVE"), true);
  }

  // Nothing to put back, or she signed out on purpose. Either way, hands off.
  {
    const r = retryRig({ now: NOW2, alive: false, cannotRestore: true });
    check("no session to restore, no retry", r.made.retry("token-gone"), false);
    check("and Save is left alone", r.log.includes("CLICKED SAVE"), false);
  }
  {
    const r = retryRig({ now: NOW2, alive: false, signedOut: true });
    check("she signed out, so it stays out", r.made.retry("token-gone"), false);
  }

  // No Save button on screen -- she is somewhere else in the editor.
  {
    const r = retryRig({ now: NOW2, alive: true, noButton: true });
    check("no button, no press", r.made.retry("token-gone"), false);
  }

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

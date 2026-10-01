/* =============================================================================
 * storage-guard.js — keep the safety net from eating the thing it protects
 * =============================================================================
 * WHY THIS EXISTS
 *
 * On 2026-10-01 she could not log in. Not a bad password, not an expired
 * session — this:
 *
 *   Failed to execute 'setItem' on 'Storage':
 *   Setting the value of 'gotrue.user' exceeded the quota.
 *
 * localStorage was full, so gotrue had nowhere to put the session, so there
 * was no way into the editor at all. What filled it was the editor's own
 * autosave safety net: a rolling history of every field of every post she
 * had touched in the last fortnight, thirty versions deep, each version a
 * complete copy of the form. One post at thirty versions is most of a
 * megabyte. Three posts is more than half of everything the browser allows.
 *
 * The safety net exists so a failed save never costs her a draft. Filling
 * the quota until she cannot sign in is a far worse version of the same
 * problem, caused by the cure.
 *
 * WHAT IT DOES
 *
 * Bounds the safety net in BYTES rather than in versions-per-post, which is
 * the only unit the browser actually cares about, and evicts across every
 * post rather than only the one being written. The old code trimmed the
 * current post's history when ITS write failed, which is backwards: the post
 * she is working on is the one worth keeping, and the space is being held by
 * the five she is not.
 *
 * Eviction drops the oldest version it can find anywhere, repeatedly, until
 * the total fits — but never below a floor, so every post keeps something
 * and the one she is in keeps plenty.
 *
 * Shared because /login/ needs it too. By the time the quota is full the
 * editor cannot be reached, so the editor cannot be where this is fixed;
 * the login page frees the space and tries again.
 *
 * Everything here tolerates localStorage throwing or being absent. A guard
 * that breaks the page it guards is not a guard.
 * ========================================================================= */
(function (w) {
  "use strict";

  var FORM_PREFIX = "editor-form:";
  // Written by a second snapshot store that was removed on 2026-09-20.
  // Nothing creates these any more; they are dropped on sight here, where
  // the point is reclaiming space rather than preserving history.
  var DEAD_PREFIXES = ["editor-snapshot:", "editor-history:"];

  // localStorage gives roughly 5MB for the whole origin, shared with gotrue's
  // session, Decap's preferences and — if IndexedDB is ever unavailable —
  // Decap's own entry backups. One megabyte is a generous share for drafts
  // and leaves the rest of it alone.
  var BUDGET = 1024 * 1024;

  // Versions kept per post even when space is short. The post she is
  // currently in keeps more, because depth matters where she is working and
  // a post she last touched a week ago needs one good copy, not eight.
  var FLOOR_OTHER = 2;
  var FLOOR_CURRENT = 8;

  function keys() {
    try { return Object.keys(w.localStorage); } catch (e) { return []; }
  }

  function get(k) {
    try { return w.localStorage.getItem(k); } catch (e) { return null; }
  }

  function drop(k) {
    try { w.localStorage.removeItem(k); } catch (e) {}
  }

  // Close enough to what the browser charges: key plus value, in UTF-16
  // units. Exactness does not matter, staying well under does.
  function bytes(k) {
    return (k || "").length + String(get(k) || "").length;
  }

  function isDead(k) {
    for (var i = 0; i < DEAD_PREFIXES.length; i++) {
      if (k.indexOf(DEAD_PREFIXES[i]) === 0) return true;
    }
    return false;
  }

  function formKeys() {
    return keys().filter(function (k) { return k.indexOf(FORM_PREFIX) === 0; });
  }

  function usage() {
    return formKeys().reduce(function (n, k) { return n + bytes(k); }, 0);
  }

  function history(k) {
    try {
      var h = JSON.parse(get(k));
      return Array.isArray(h) ? h : null;
    } catch (e) { return null; }
  }

  // What is actually taking up the room, biggest first. For the console.
  function report() {
    return keys().map(function (k) {
      var h = history(k);
      return { key: k, kb: Math.round(bytes(k) / 1024), versions: h ? h.length : null };
    }).sort(function (a, b) { return b.kb - a.kb; });
  }

  function sweepDead() {
    var freed = 0;
    keys().forEach(function (k) {
      if (!isDead(k)) return;
      freed += bytes(k);
      drop(k);
    });
    return freed;
  }

  // Bring the safety net under budget. `current` is the key being written,
  // which is protected by the higher floor. Returns bytes freed.
  function evict(current, budget) {
    budget = (typeof budget === "number") ? budget : BUDGET;
    var freed = sweepDead();

    // A key holding something that is not a version array is not something
    // this understands well enough to trim. Drop it: it is ours by prefix,
    // and an unreadable history is not a history.
    formKeys().forEach(function (k) {
      if (history(k) === null) { freed += bytes(k); drop(k); }
    });

    var guard = 0;
    while (usage() > budget && guard++ < 500) {
      var victim = null, victimAge = Infinity, victimHist = null;

      formKeys().forEach(function (k) {
        var h = history(k);
        if (!h || !h.length) return;
        var floor = (k === current) ? FLOOR_CURRENT : FLOOR_OTHER;
        if (h.length <= floor) return;              // leave it something
        var age = (h[0] && h[0].ts) || 0;           // oldest version in this key
        if (age < victimAge) { victimAge = age; victim = k; victimHist = h; }
      });

      if (!victim) break;                           // everything is at its floor

      var before = bytes(victim);
      victimHist.shift();
      try {
        w.localStorage.setItem(victim, JSON.stringify(victimHist));
      } catch (e) {
        drop(victim);                               // cannot shrink it; let it go
      }
      freed += before - bytes(victim);
    }
    return freed;
  }

  // The emergency: storage is full and something that is not ours needs to
  // write. Take the floors down to one apiece and clear what we can.
  function freeSpaceNow() {
    var freed = sweepDead();
    FLOOR_OTHER = 1;
    FLOOR_CURRENT = 1;
    freed += evict(null, 0);
    FLOOR_OTHER = 2;
    FLOOR_CURRENT = 8;
    return freed;
  }

  // Does this error mean the browser ran out of room? Chrome, Firefox and
  // Safari each word it differently, and Safari's private mode throws a
  // quota error for every write regardless of how much is stored.
  function isQuotaError(err) {
    if (!err) return false;
    var name = err.name || "";
    var msg = (err.message || String(err));
    return name === "QuotaExceededError" ||
           name === "NS_ERROR_DOM_QUOTA_REACHED" ||
           /quota|exceeded the quota|storage is full/i.test(msg);
  }

  w.__STORAGE_GUARD = {
    BUDGET: BUDGET,
    bytes: bytes,
    usage: usage,
    report: report,
    sweepDead: sweepDead,
    evict: evict,
    freeSpaceNow: freeSpaceNow,
    isQuotaError: isQuotaError
  };

  // A one-liner for the console when something has gone wrong and the
  // question is "what is using the space".
  w.STORAGE_REPORT = function () {
    var rows = report();
    console.log("safety net: " + Math.round(usage() / 1024) + " KB of a " +
                Math.round(BUDGET / 1024) + " KB budget");
    rows.forEach(function (r) {
      console.log("  " + r.kb + " KB  " + r.key +
                  (r.versions === null ? "" : "  (" + r.versions + " versions)"));
    });
    return rows.length + " keys";
  };
})(window);

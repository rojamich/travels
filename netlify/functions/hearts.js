// =============================================================================
// hearts.js — per-post heart/like counter (Netlify Function + Blobs)
// =============================================================================
// GET  /.netlify/functions/hearts?slug=<post-slug>   → { count: N }
// POST /.netlify/functions/hearts?slug=<post-slug>   → { count: N+1 }
//
// Same shape as views.js. The client-side heart button enforces "one
// heart per browser" via localStorage, so a reader can't spam the
// counter from the UI. Someone determined enough could POST directly
// via curl, but for a personal travel blog that's fine — the worst
// case is a fake +10 that we shrug at.
//
// No auth. No user identity tracked. Just a running integer per slug.
// =============================================================================

import { getStore } from "@netlify/blobs";

export default async (req) => {
  const url = new URL(req.url);
  const slug = normaliseSlug(url.searchParams.get("slug"));
  if (!slug) {
    return json({ error: "missing or invalid slug" }, 400);
  }

  const store = getStore("post-hearts");

  if (req.method === "POST") {
    const current = parseInt(await store.get(slug) || "0", 10) || 0;
    const next = current + 1;
    await store.set(slug, String(next));
    return json({ count: next });
  }

  if (req.method === "DELETE") {
    // Undo a previous heart. Floor at 0 so accidental spam-clicks
    // (or someone hitting DELETE without having POSTed) can never
    // produce a negative count.
    const current = parseInt(await store.get(slug) || "0", 10) || 0;
    const next = Math.max(0, current - 1);
    await store.set(slug, String(next));
    return json({ count: next });
  }

  if (req.method === "GET") {
    const current = parseInt(await store.get(slug) || "0", 10) || 0;
    return json({ count: current });
  }

  return json({ error: "method not allowed" }, 405);
};

// The slug arrives as Jekyll's page.id (comments) or page.slug (hearts,
// views), and Jekyll percent-encodes anything outside ASCII. The Armenia
// trip reaches us spelled
//
//     between-mountains-monasteries-%E2%9B%B0%EF%B8%8F%F0%9F%8F%B0/...
//
// which the query string encodes AGAIN on the way, so what arrives here after
// one automatic decode still carries literal % characters. Blocking % (which
// is what stops a double-encoded traversal) therefore blocked the very posts
// this was meant to fix.
//
// So decode once more, and key the store on the decoded form. A post then has
// ONE key however its name was spelled coming in — the percent-encoded
// spelling the page sends and the plain one a hand-written request might use
// both land on the same comments. Anything still holding a % after that is
// someone encoding their encoding, and invalidSlug refuses it.
function normaliseSlug(raw) {
  if (typeof raw !== "string" || !raw) return null;
  let slug = raw;
  if (slug.includes("%")) {
    try {
      slug = decodeURIComponent(slug);
    } catch (e) {
      return null;   // malformed escape, e.g. "%zz"
    }
  }
  return invalidSlug(slug) ? null : slug;
}

// -----------------------------------------------------------------------------
// Is this one of our own post paths?
// -----------------------------------------------------------------------------
// A slug names one of our own posts. Anything else is somebody poking at the
// endpoint: every write creates a blob under whatever key it is given, so
// without a bound on shape and length the store fills with junk that nothing
// on the site will ever read — invisible, since the dashboard only lists slugs
// from the search index, and still costing storage.
//
// This used to be an allowlist of /^[a-z0-9_\-\/.]+$/i, on the assumption that
// a Jekyll slug is lowercase words and dashes. It is not. Jekyll keeps what
// the title and the trip name contain, and this site's contain plenty:
//
//     vietnam/bánh-cuốn-ha-long-bay                    Vietnamese diacritics
//     fjords-forever/oslo-to-flåm-train-travel         å
//     fjords-forever/lofoten-️-bodø-️-oslo              ø, and a stray U+FE0F
//     between-mountains-monasteries-⛰️🏰/…              emoji in the TRIP name,
//                                                      so all 8 of its posts
//
// Eleven posts were answered 400 by every one of these functions. On a post
// with an accented title the heart and view counters had been showing a dash
// since the day it was written; on the Armenia trip the comment box could not
// load or accept a note, which is how this came to light — a reader was told
// "missing or invalid slug" when they tried to leave one.
//
// So: a blocklist, not an allowlist. What actually matters for a blob key is
// that it cannot climb out of its own namespace, cannot carry control
// characters or whitespace, cannot be read as a second path or a query, and
// cannot be unbounded. Letters and pictures are none of those things.
//
// The longest real slug today is 120 characters ("war-memorial-of-korea-…"),
// which the old cap allowed by a single character. 200 leaves actual room.
function invalidSlug(slug) {
  return !slug ||
         slug.length > 200 ||
         slug.includes("..") ||
         slug.startsWith("/") ||
         slug.endsWith("/") ||
         // Control characters, whitespace, and the characters that would let a
         // slug pose as a path, a query or an encoding of one.
         /[\u0000-\u001F\u007F\\?#%\s]/.test(slug);
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store"
    }
  });
}

export const config = {
  path: "/.netlify/functions/hearts"
};

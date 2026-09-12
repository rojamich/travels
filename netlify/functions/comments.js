// =============================================================================
// comments.js — per-post comments (Netlify Function + Blobs)
// =============================================================================
// Replaces Cusdis, which was archived by its author on 2026-07-17 and whose
// hosted service now answers 521 to everything. Same promise as before —
// a reader types a name and a message, no signup, no account — but the data
// is ours and lives in the same Netlify Blobs store the hearts and views
// counters already use.
//
// PUBLIC
//   GET  /.netlify/functions/comments?slug=<post-slug>
//        → { comments: [ { id, name, body, at }, ... ] }   approved only,
//          oldest first, so a thread reads top to bottom.
//   POST /.netlify/functions/comments?slug=<post-slug>
//        body { name, body, website }  → { ok: true }
//        The comment is stored UNAPPROVED. Nothing a stranger writes appears
//        on the site until one of us approves it from /admin-comments/.
//        `website` is a honeypot: a real person never sees the field, so
//        anything that fills it is a bot. We answer 200 and throw it away —
//        telling a bot it failed only teaches it to try again differently.
//
// ADMIN — needs a Netlify Identity login, the same one as /admin/
//   GET    ?admin=1            → { comments: [...] } every comment on every
//          post, approved or not, each carrying its slug. /admin-comments/
//          splits them into "waiting for you" and "published".
//   PATCH  ?slug=<s>&id=<id>   → approve it (it appears on the post)
//   DELETE ?slug=<s>&id=<id>   → delete it for good
//
// The admin routes verify the caller's Identity token against
// /.netlify/identity/user before doing anything — this is the approach
// _includes/admin-gate.html describes as the real lock, as opposed to the
// browser-side gate that only hides a page.
//
// STORAGE SHAPE
// One blob per slug holding a JSON array, rather than one blob per comment.
// A thread is then a single get instead of a list plus N gets, which is what
// every reader of a post pays for. The cost is that two people commenting on
// the same post in the same second could have one overwrite the other —
// read-modify-write with no locking, exactly as in hearts.js. On a family
// travel blog that is a trade worth making.
// =============================================================================

import { getStore } from "@netlify/blobs";

// A name has to fit on a line and a note has to stay a note. These are also
// what stops one POST from filling the store: a slug's blob cannot exceed
// roughly MAX_PER_POST × (MAX_BODY + MAX_NAME) bytes.
const MAX_NAME = 60;
const MAX_BODY = 2000;
const MAX_PER_POST = 300;
// A flood of junk awaiting moderation is still a flood. Once this many
// comments on one post are unapproved, that post stops accepting more until
// we have worked through them.
const MAX_PENDING_PER_POST = 40;
// Real notes from family do not carry three links. Spam almost always does.
const MAX_LINKS = 2;

export default async (req) => {
  const url = new URL(req.url);
  // Strong consistency, not the default.
  //
  // Netlify Blobs reads are eventually consistent unless you ask otherwise:
  // a write is guaranteed visible everywhere within 60 seconds, and may not
  // be before that. For a view counter that is nothing. Here it is a way to
  // lose what people wrote, because every write in this file is a
  // read-modify-write of the WHOLE array for a post:
  //
  //   posting     reads the array, appends, writes it back
  //   approving   reads the array, flips one flag, writes it back
  //   deleting    reads the array, removes one, writes it back
  //
  // On a stale read each of those writes back a stale array. Approving a
  // comment could resurrect one deleted a moment earlier; deleting one could
  // undo an approval; a second comment arriving inside the window could erase
  // the first. Moderating is also a read-then-decide loop, and it has to see
  // the store as it actually is.
  //
  // The cost is slower reads. One call per post view, on a box that is now
  // only fetched when it is nearly on screen — worth it to not drop a note
  // from somebody's grandmother.
  const store = getStore({ name: "post-comments", consistency: "strong" });

  // ----- admin routes -------------------------------------------------
  if (url.searchParams.get("admin") === "1") {
    if (!(await isEditor(req, url))) return json({ error: "not authorised" }, 401);
    return json({ comments: await everything(store) });
  }

  if (req.method === "PATCH" || req.method === "DELETE") {
    if (!(await isEditor(req, url))) return json({ error: "not authorised" }, 401);
    return moderate(req, url, store);
  }

  // ----- public routes ------------------------------------------------
  const slug = normaliseSlug(url.searchParams.get("slug"));
  if (!slug) {
    return json({ error: "missing or invalid slug" }, 400);
  }

  if (req.method === "GET") {
    const all = await read(store, slug);
    return json({
      comments: all
        .filter((c) => c.approved)
        .map(({ id, name, body, at }) => ({ id, name, body, at }))
    });
  }

  if (req.method === "POST") {
    let payload;
    try {
      payload = await req.json();
    } catch {
      return json({ error: "expected JSON" }, 400);
    }

    // The honeypot. Answer as though it worked, store nothing.
    if (payload.website) return json({ ok: true });

    const name = clean(payload.name, MAX_NAME);
    const body = clean(payload.body, MAX_BODY);
    if (!name) return json({ error: "please add your name" }, 400);
    if (!body) return json({ error: "please write a message" }, 400);
    if (countLinks(body) > MAX_LINKS) {
      return json({ error: "that's a lot of links — please write us a note instead" }, 400);
    }

    const all = await read(store, slug);
    if (all.length >= MAX_PER_POST) {
      return json({ error: "this post has all the comments it can hold" }, 429);
    }
    if (all.filter((c) => !c.approved).length >= MAX_PENDING_PER_POST) {
      return json({ error: "we're behind on reading these — try again in a day or two" }, 429);
    }

    all.push({
      id: newId(),
      name,
      body,
      at: new Date().toISOString(),
      approved: false
    });
    await store.setJSON(slug, all);

    return json({ ok: true });
  }

  return json({ error: "method not allowed" }, 405);
};

// -----------------------------------------------------------------------------
// Moderation
// -----------------------------------------------------------------------------
async function moderate(req, url, store) {
  const slug = normaliseSlug(url.searchParams.get("slug"));
  const id = url.searchParams.get("id");
  if (!slug || !id) return json({ error: "need slug and id" }, 400);

  const all = await read(store, slug);
  const i = all.findIndex((c) => c.id === id);
  if (i === -1) return json({ error: "no such comment" }, 404);

  if (req.method === "PATCH") {
    all[i].approved = true;
  } else {
    all.splice(i, 1);
  }

  // Don't leave an empty array sitting in the store once the last comment on
  // a post is deleted — that is a blob whose only content is "[]".
  if (all.length === 0) await store.delete(slug);
  else await store.setJSON(slug, all);

  return json({ ok: true });
}

// Every comment on every post, each tagged with the post it belongs to.
// Same shape as counts.js uses for the rankings page: one list() plus a get()
// per post, which is fine at this size and keeps the page to one request.
async function everything(store) {
  const { blobs } = await store.list();
  const perSlug = await Promise.all(
    (blobs || []).map(async (b) => {
      const all = await read(store, b.key);
      return all.map((c) => ({ ...c, slug: b.key }));
    })
  );
  // Oldest first, so working down the list is working through the backlog.
  return perSlug.flat().sort((a, b) => a.at.localeCompare(b.at));
}

// -----------------------------------------------------------------------------
// Is the caller one of us?
// -----------------------------------------------------------------------------
// Netlify Identity hands the browser a JWT. We don't try to verify the
// signature ourselves — we hand the token straight back to Identity's own
// /user endpoint, which answers 200 with the account only if the token is
// genuine and unexpired. One request, nothing to keep in sync, no secret to
// store.
async function isEditor(req, url) {
  const auth = req.headers.get("authorization") || "";
  if (!/^Bearer \S+$/.test(auth)) return false;

  const origin = process.env.URL || url.origin;
  try {
    const res = await fetch(`${origin}/.netlify/identity/user`, {
      headers: { authorization: auth }
    });
    return res.ok;
  } catch {
    // Identity unreachable. Fail closed — the same choice admin-gate.html
    // makes when its widget won't load.
    return false;
  }
}

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
// Kept identical to the check in hearts.js and views.js — the three endpoints
// are handed the same kind of name and should agree on what one looks like.
//
// It used to be an allowlist of /^[a-z0-9_\-\/.]+$/i, on the assumption that
// a Jekyll slug is lowercase words and dashes. It is not. Jekyll keeps what
// the title and the trip name contain, and this site's contain plenty:
//
//     vietnam/bánh-cuốn-ha-long-bay                    Vietnamese diacritics
//     fjords-forever/oslo-to-flåm-train-travel         å
//     fjords-forever/lofoten-️-bodø-️-oslo              ø, and a stray U+FE0F
//     between-mountains-monasteries-⛰️🏰/…              emoji in the TRIP name,
//                                                      so all 8 of its posts
//
// Eleven posts were answered 400 by all three functions. A reader trying to
// leave a note on the Armenia trip was told "missing or invalid slug", which
// is how this came to light; the thread above the form failed to load for the
// same reason. On the posts with accented titles the heart and view counters
// had been showing a dash since the day each was written.
//
// So: a blocklist, not an allowlist. What matters for a blob key is that it
// cannot climb out of its own namespace, cannot carry control characters or
// whitespace, cannot be read as a second path or a query, and cannot be
// unbounded. Letters and pictures are none of those things.
//
// The longest real slug today is 120 characters, which the old cap allowed by
// a single character. 200 leaves actual room.
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

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------
async function read(store, slug) {
  try {
    const all = await store.get(slug, { type: "json" });
    return Array.isArray(all) ? all : [];
  } catch {
    // A blob that isn't valid JSON shouldn't take a post's comment box down.
    return [];
  }
}

// Trim, cap the length, and drop control characters — the page renders these
// with textContent so markup is inert either way, but a stray NUL or a line
// of backspaces has no business being stored.
function clean(value, max) {
  if (typeof value !== "string") return "";
  return value
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "")
    .trim()
    .slice(0, max);
}

function countLinks(text) {
  return (text.match(/https?:\/\/|www\./gi) || []).length;
}

function newId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
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
  path: "/.netlify/functions/comments"
};

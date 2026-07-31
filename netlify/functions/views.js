// =============================================================================
// views.js — per-post view counter (Netlify Function + Blobs)
// =============================================================================
// GET  /.netlify/functions/views?slug=<post-slug>    → { count: N }
// POST /.netlify/functions/views?slug=<post-slug>    → { count: N+1 }
//
// Stores counts in a Netlify Blobs store keyed by the post slug. Free
// tier is 1GB storage / 10GB egress, way more than we'll ever use for
// integer counters (a slug + 6-digit count is ~50 bytes each).
//
// GET is safe for anyone to hit; POST is the "increment" call. The
// client-side widget calls POST at most once per browser session
// (session-storage gate) so page reloads in the same tab don't inflate
// the count.
//
// No auth on either endpoint — anyone visiting the site can read/
// increment. That's fine: the write path just bumps an integer, there's
// nothing to leak or corrupt beyond an inflated view count.
// =============================================================================

import { getStore } from "@netlify/blobs";

export default async (req) => {
  const url = new URL(req.url);
  const slug = url.searchParams.get("slug");
  if (!slug || !/^[a-z0-9_\-\/.]+$/i.test(slug)) {
    return json({ error: "missing or invalid slug" }, 400);
  }

  const store = getStore("post-views");

  if (req.method === "POST") {
    // Racy increment — two overlapping POSTs could clobber each other.
    // In practice for our traffic it's a non-issue; if it ever matters
    // we can move to Netlify Blobs' consistency: "strong" get/set with
    // a retry loop. For now, simple wins.
    const current = parseInt(await store.get(slug) || "0", 10) || 0;
    const next = current + 1;
    await store.set(slug, String(next));
    return json({ count: next });
  }

  if (req.method === "GET") {
    const current = parseInt(await store.get(slug) || "0", 10) || 0;
    return json({ count: current });
  }

  return json({ error: "method not allowed" }, 405);
};

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json",
      // Keep responses fresh — counts change frequently.
      "cache-control": "no-store"
    }
  });
}

export const config = {
  path: "/.netlify/functions/views"
};

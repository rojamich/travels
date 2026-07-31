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
  const slug = url.searchParams.get("slug");
  if (!slug || !/^[a-z0-9_\-\/.]+$/i.test(slug)) {
    return json({ error: "missing or invalid slug" }, 400);
  }

  const store = getStore("post-hearts");

  if (req.method === "POST") {
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
      "cache-control": "no-store"
    }
  });
}

export const config = {
  path: "/.netlify/functions/hearts"
};

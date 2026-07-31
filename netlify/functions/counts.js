// =============================================================================
// counts.js — bulk fetch of view + heart counts for the admin dashboard
// =============================================================================
// GET /.netlify/functions/counts
//   → { "post-slug-1": { views: 42, hearts: 3 }, "post-slug-2": {...}, ... }
//
// One request pulls every count from both stores instead of 2×N calls
// from the client. Used by /admin-stats/ to rank posts by views/hearts.
//
// No auth. The exact counts are already fetchable per-slug via
// views.js / hearts.js, so listing them all in bulk doesn't leak
// anything new — just makes the ranking view cheap.
// =============================================================================

import { getStore } from "@netlify/blobs";

export default async (req) => {
  if (req.method !== "GET") {
    return json({ error: "method not allowed" }, 405);
  }

  const viewsStore = getStore("post-views");
  const heartsStore = getStore("post-hearts");

  const [viewsList, heartsList] = await Promise.all([
    viewsStore.list(),
    heartsStore.list()
  ]);

  // Union of every slug we've ever tracked in either store.
  const slugs = new Set();
  (viewsList.blobs || []).forEach((b) => slugs.add(b.key));
  (heartsList.blobs || []).forEach((b) => slugs.add(b.key));

  const result = {};
  await Promise.all(
    Array.from(slugs).map(async (slug) => {
      const [v, h] = await Promise.all([
        viewsStore.get(slug),
        heartsStore.get(slug)
      ]);
      result[slug] = {
        views: parseInt(v || "0", 10) || 0,
        hearts: parseInt(h || "0", 10) || 0
      };
    })
  );

  return json(result);
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
  path: "/.netlify/functions/counts"
};

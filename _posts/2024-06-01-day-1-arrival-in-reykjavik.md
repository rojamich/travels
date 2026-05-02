---
# =============================================================================
# A BLOG POST — anatomy explained
# =============================================================================
# Every post is a Markdown file in _posts/. The filename MUST be:
#   YYYY-MM-DD-some-url-slug.md
# The date in the filename is what Jekyll uses to publish the post.
#
# Everything between the two `---` lines is "front matter" — metadata about
# the post. Everything after the second `---` is the actual post content,
# written in Markdown.
# =============================================================================

# --- The headline shown on the page and in listings ---
title: "Day 1 — Arrival in Reykjavik"

# --- Publish date. Use ISO format (YYYY-MM-DD). Time is optional. ---
date: 2024-06-01

# --- Which trip this post belongs to. ---
# Must match the `slug` in _data/trips.yml exactly.
categories:
  - iceland-2024

# --- Display order WITHIN this trip. ---
# Posts are sorted by this number on the trip page. Lower = earlier.
# This lets you reorder posts even if you didn't write them in trip order.
order: 1

# --- The cover photo for this day. ---
# `teaser` shows in listings (homepage, trip page).
# `overlay_image` shows as a big banner at the top of the post itself.
# `overlay_filter` darkens the banner so the title text stays readable
#   (0.0 = no darkening, 1.0 = fully black). 0.3 is a good default.
header:
  teaser: https://picsum.photos/seed/iceland1/800/500
  overlay_image: https://picsum.photos/seed/iceland1/1600/600
  overlay_filter: 0.4

# --- Optional tags for cross-trip search ---
tags:
  - iceland
  - reykjavik
  - arrival

# --- Optional location (used to draw a pin on the trip map). ---
# Get coordinates from https://www.latlong.net/ — search for the place,
# copy the lat and lng. Posts without `location:` simply don't get a pin.
location:
  name: "Reykjavik, Iceland"
  lat: 64.1466
  lng: -21.9426

# --- Photo gallery for this post (optional). ---
# Each entry needs `url` (full size) and `image_path` (thumbnail).
# Usually the same image. Fill in `alt` for accessibility.
gallery:
  - url: https://picsum.photos/seed/iceland1a/1200/800
    image_path: https://picsum.photos/seed/iceland1a/600/400
    alt: "Reykjavik harbor at golden hour"
  - url: https://picsum.photos/seed/iceland1b/1200/800
    image_path: https://picsum.photos/seed/iceland1b/600/400
    alt: "Hallgrimskirkja church"
  - url: https://picsum.photos/seed/iceland1c/1200/800
    image_path: https://picsum.photos/seed/iceland1c/600/400
    alt: "Colorful houses downtown"

# --- An "excerpt" shown in listings. If you don't set one, Jekyll uses
#     the first paragraph of the post automatically. ---
excerpt: "Touchdown in Keflavik at 6 AM, picked up the rental, and got our first taste of Iceland's wide-open landscapes on the drive into Reykjavik."
---

<!--
  THE POST BODY STARTS HERE. Written in Markdown.
  Quick syntax cheat sheet:
    **bold**      *italic*       [link text](https://example.com)
    # Big heading       ## Smaller heading        ### Smaller still
    - bullet item
    1. numbered item
    > quoted text
    ![alt text](path/to/image.jpg)        ← inline image
-->

We landed in Keflavik just before 6 AM after the redeye from Boston. Half asleep, we
stumbled through customs, picked up the rental car, and pointed it east toward
Reykjavik. The landscape on that 45-minute drive was our first hint that this trip was
going to be unlike anywhere we'd been: black volcanic rock all the way to the horizon,
not a tree in sight, the sun already high in the sky despite the early hour.

## Settling in

Our Airbnb wasn't ready until 3 PM, so we did what every jet-lagged traveler does and
went looking for coffee. **Reykjavik Roasters** in the city center turned out to be
exactly what we needed.

> "First espresso of the trip. Already plotting how to come back."

After caffeine, we walked the entire downtown loop — about an hour at a slow pace —
and ended up at Hallgrimskirkja, the towering church that dominates the skyline.

## Photo gallery

<!--
  This single line generates a photo gallery from the `gallery:` field in
  the front matter above. Minimal Mistakes handles the layout automatically.
-->
{% include gallery caption="Wandering Reykjavik on day one." %}

## Embedding a video

To include a video, just paste a YouTube embed in the post like this:

<!--
  This is a real YouTube embed. Replace the URL with any YouTube video.
  The trick: get the video ID (the part after v=) and put it in the URL
  after /embed/. So https://www.youtube.com/watch?v=ABC123 becomes
  https://www.youtube.com/embed/ABC123
-->

<iframe width="100%" height="400"
  src="https://www.youtube.com/embed/dQw4w9WgXcQ"
  frameborder="0"
  allowfullscreen></iframe>

That's it for day one. Tomorrow: the Golden Circle.

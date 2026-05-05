# How to Post a New Travel Entry

This guide is the everyday "I just got back from the day, want to write it up" workflow.
You only ever need this page.

You do **everything from a web browser**. No code editor, no terminal, no installs.

---

## The 30-second version

1. Go to **https://where-in-the-world-are-mike-and-jen.netlify.app/admin/**
2. Log in with your email and password (the first time, click your invitation link from the email Netlify sent you and set a password).
3. Click **"New Travel Post"** in the top-right.
4. Fill in the form — title, date, trip, day order, etc.
5. Drag photos into the **Cover**, **Banner**, and **Gallery** fields. They upload automatically (no compression needed — Cloudinary handles it).
6. Write your post in the big **Body** box at the bottom.
7. Click **Save** as often as you want while writing — your changes are saved as a draft and **don't go live yet**.
8. When the post is finished and you want it visible to the world, click the **Status** dropdown → **Ready**, then click **Publish**.
9. Within ~1 minute the post is live on the site.

That's it.

## Save vs Publish

This is the most important thing to understand:

- **Save** = saves a draft. Doesn't trigger a build. Doesn't go live. Free to do as often as you want — every paragraph, every photo, every spelling fix. Drafts persist between sessions, so you can save and come back tomorrow.
- **Publish** = puts the post live on the website. Costs one "build credit" each time. Use this when the post is genuinely done.

Same applies to edits on existing posts — you can save many revisions of an edit without each one triggering a rebuild. Only the final Publish click matters.

The **Workflow** tab in the left navigation shows all your unpublished drafts as cards. Drag a card from "Draft" → "In Review" → "Ready" if you like to mark progress, or just go straight to Publish when ready.

---

## What each field on the form means

| Field | What to put |
|-------|-------------|
| **Title** | The headline of the post — e.g. "Day 3 — The South Coast" |
| **Date** | The date this happened (format YYYY-MM-DD; the date picker handles it) |
| **Trip** | Pick which trip this post belongs to from the dropdown |
| **Day order in trip** | 1 for day 1, 2 for day 2, etc. Posts on the trip page sort by this — so you can reorder days even after writing them out of order |
| **Cover & banner → Teaser** | The small thumbnail shown in the homepage and trip-page listings |
| **Cover & banner → Banner** | The big photo at the top of the post itself (often the same as Teaser) |
| **Cover & banner → Banner darkening** | 0 = no darkening, 1 = fully black. Higher numbers make the title text more readable on bright photos. 0.4 is the default sweet spot |
| **Tags** | Optional keywords (food, hiking, etc). Skip if you don't care |
| **Map pin location** | Where this day happened. Adds a clickable pin on the map. Click "Add Map pin location" to expand, then fill in name + lat + lng (get coords from [latlong.net](https://www.latlong.net/)). Skip the whole block for travel/rest days |
| **Photo gallery** | Photos shown together as a grid. Click "Add Photo gallery" then "Add" once per photo. The two image fields can be the same photo |
| **Excerpt** | Optional one-sentence summary shown in listings |
| **Body** | The actual blog post. The toolbar above the box has buttons for bold, italic, headings, links, etc. Drag photos in to add them inline |

---

## Editing or deleting an existing post

1. Same admin page, click any post in the list to open it.
2. Make your changes — change works exactly like creating a new post.
3. Click **Publish** to save (or **Delete** at the bottom to remove).
4. Goes live within a minute.

---

## "Help, I broke something"

The admin form prevents most kinds of breakage — you can't accidentally delete the site or mess up the structure.

If a published post looks weird, just open it in admin and fix it. If you can't figure out what's wrong, send your husband the link to the post and he can look at the file directly.

Nothing you can do in admin will permanently break anything; everything is in Git history and can be undone.

---

## (Advanced) Direct file template — only if admin is unavailable

If you ever can't log in to admin, you can still post by editing the GitHub repo directly. Skip this section unless you need it.

```markdown
---
title: "Day 3 — The South Coast"
date: 2024-06-03
categories:
  - iceland-2024
order: 3
header:
  teaser: /assets/images/iceland-2024/day3-cover.jpg
  overlay_image: /assets/images/iceland-2024/day3-cover.jpg
  overlay_filter: 0.4
tags:
  - iceland
  - waterfalls
location:
  name: "Vík, Iceland"
  lat: 63.4194
  lng: -19.0064
gallery:
  - url: /assets/images/iceland-2024/day3-photo1.jpg
    image_path: /assets/images/iceland-2024/day3-photo1.jpg
    alt: "what this photo shows"
  - url: /assets/images/iceland-2024/day3-photo2.jpg
    image_path: /assets/images/iceland-2024/day3-photo2.jpg
    alt: "what this photo shows"
excerpt: "One-sentence teaser shown in the trip listing."
---

Write your post here.

You can use **bold**, *italic*, and [links](https://example.com).

## A subheading

Another paragraph.

{% include gallery caption="A few favorites from the day." %}
```

### What to change in the template

| Field | What to put |
|-------|-------------|
| `title:` | The headline of the post. Keep the quotes around it. |
| `date:` | YYYY-MM-DD — must match the date in the filename |
| `categories:` | The trip's slug (e.g. `iceland-2024`). Just one. |
| `order:` | A number controlling sequence on the trip page. Day 1 is `1`, day 2 is `2`, etc. |
| `header:` images | Path to the post's cover photo (see "Adding photos" below) |
| `tags:` | Optional keywords. Leave empty or delete if you don't care. |
| `location:` | Where this day happened. Becomes a clickable pin on the trip map (see "Putting a post on the map" below). Delete the whole block if you don't want a pin for this day. |
| `gallery:` | One block per gallery photo. Add or remove blocks as needed. |
| `excerpt:` | One-sentence summary shown in listings |
| Body | Everything below the second `---`. This is your actual blog post. |

---

## Adding photos

You don't compress, you don't resize, you don't upload to a folder. Just **drag photos straight into the form.**

When you click an image field (Cover, Banner, Gallery rows) or drag a photo into one, the photo uploads to Cloudinary in the background. Cloudinary stores the original AND automatically generates an optimized smaller version that the website serves to visitors. Result: visitors see fast-loading photos without you doing any work.

To put a photo inline in the post body (in the middle of your writing, not in a gallery), click the image button in the body editor's toolbar.

### How many photos can I add?

Cloudinary's free plan gives ~25 GB of photos and 25 GB/month of bandwidth. At your typical 20 photos per post, that's around 500–1000 posts before storage becomes a concern. Realistically: years and years.

---

## Adding videos

YouTube and Vimeo are free, work great with the site, and don't count
against any storage. Upload the video to YouTube (mark it Unlisted if it's
just for family), then in the body editor click the **HTML** button (or
type directly) and paste:

```html
<iframe src="https://www.youtube.com/embed/VIDEO_ID_HERE"
  frameborder="0"
  allowfullscreen></iframe>
```

(No need to set width or height — the site auto-caps videos at a clean
640-pixel-wide 16:9 size, regardless of how you embed them.)

To get the `VIDEO_ID`: from a YouTube URL like
`https://www.youtube.com/watch?v=dQw4w9WgXcQ`, the ID is `dQw4w9WgXcQ`.

---

## Reordering posts within a trip

Just edit the `order:` number in each post's front matter. The trip page
sorts by that number, lowest first. So if you want the "rest day" you wrote
later to appear between Day 4 and Day 5, give it `order: 4.5`.

---

## Editing an existing post

1. Browse to the post file on GitHub
2. Click the pencil icon (top right of the file view) → "Edit this file"
3. Make your changes
4. Scroll down → **Commit changes**

The edit goes live within a minute, same as new posts.

---

## "Help, I broke something"

If a post stops appearing or the site looks weird, the most common cause is
a typo in the front matter — usually a missing colon or quote mark.

Send the link of the file you edited to your husband and he can fix it in
under a minute. Nothing you can do in the editor will permanently break
anything; everything is in Git history and can be undone.

---

# Cheat sheet — formatting your post

Everything in the post body uses **Markdown**, a way of writing that turns
into pretty HTML automatically. You don't need to remember everything below
— just keep this guide open in another tab while you write.

## Text basics

| You type | You get |
|----------|---------|
| `**bold**` | **bold** |
| `*italic*` | *italic* |
| `***both***` | ***both*** |
| `~~strikethrough~~` | ~~strikethrough~~ |
| `> a quoted line` | a callout block, indented and visually offset |
| `---` on its own line | a horizontal divider line |

## Headings

```
# Day 4 Highlights         (biggest — only use one per post)
## A subsection
### A smaller subsection
```

## Links

```
Check out the [official site](https://example.com).
```

## Lists

```
- Bullet one
- Bullet two
  - A nested bullet
- Bullet three

1. First step
2. Second step
3. Third step
```

## Images and galleries

To put a single photo inline (right where you put it in the text):

```
![Sunset over the harbor](/assets/images/iceland-2024/sunset.jpg)
```

For a multi-photo gallery, set up the photos in the front matter under
`gallery:` (see the template at the top of this guide), then drop this
single line wherever you want the gallery to appear:

```
{% include gallery caption="A few favorites from the day." %}
```

## Emoji 🌴

Just paste them straight from your phone keyboard or Windows emoji picker
(Win + .) into the post — they work as-is.

You can also type emoji shortcodes which get converted automatically:

| Shortcode | Result |
|-----------|--------|
| `:airplane:` | ✈️ |
| `:camera:` | 📷 |
| `:earth_americas:` | 🌎 |
| `:mountain:` | 🏔️ |
| `:beach_umbrella:` | 🏖️ |
| `:hiking_boot:` | 🥾 |
| `:fork_and_knife:` | 🍴 |
| `:wine_glass:` | 🍷 |
| `:sunny:` | ☀️ |
| `:rainbow:` | 🌈 |
| `:heart:` | ❤️ |
| `:sparkles:` | ✨ |

Full list of shortcodes: [emoji-cheat-sheet.com](https://www.emoji-cheat-sheet.com/).

## Colored text

Markdown doesn't have built-in colors, but you can drop in a tiny piece
of HTML for emphasis. **Use sparingly** — too many colors makes a post
look like a ransom note.

```
This was <span style="color:#1F4858;"><strong>incredible</strong></span>.
```

That gives you a single navy-bold word inside the sentence. Other handy
hex codes that match the site palette:

| Color | Hex | Try it for |
|-------|-----|------------|
| Navy (primary) | `#1F4858` | Strong emphasis |
| Sea-glass green | `#7FB3A2` | Tag-like highlights |
| Sand warm | `#E8DCC4` | Background of a callout (see below) |
| Muted gray | `#6B7E85` | Soft side-notes |

You can also add a colored background:

```
<span style="background:#FFF4C4; padding:0 0.3em;">important note</span>
```

…which renders as <span style="background:#FFF4C4; padding:0 0.3em;">important note</span>.

## Callout boxes

For "tip" or "warning" boxes, wrap the text in a styled div:

```
<div style="background:#E8DCC4; border-left:4px solid #1F4858; padding:1em; border-radius:6px; margin:1em 0;">
  <strong>Tip:</strong> book the Blue Lagoon in advance — same-day tickets
  are usually sold out.
</div>
```

## Highlighted text

```
==This is highlighted== text.
```

> Note: highlight (`==text==`) only renders in some markdown processors.
> If it doesn't work, fall back to the colored-background span above.

## Footnotes

```
This trip was unforgettable.[^1]

[^1]: Especially the day we got stranded at the gas station.
```

## Tables

```
| Day | Where | Highlight |
|-----|-------|-----------|
| 1   | Reykjavik | Coffee, walking |
| 2   | Golden Circle | Geysir + Gullfoss |
```

Renders as a clean little table on the page.

## Embedding videos

Paste this anywhere, replacing `VIDEO_ID` with the YouTube video's ID
(the bit after `?v=` in the URL):

```
<iframe width="100%" height="400"
  src="https://www.youtube.com/embed/VIDEO_ID"
  frameborder="0"
  allowfullscreen></iframe>
```

## Putting a post on the map

If you add a `location:` block to a post's front matter, the post becomes
a clickable pin on the trip's map (and on the world map's zoom-in view):

```yaml
location:
  name: "Reykjavik, Iceland"
  lat: 64.1466
  lng: -21.9426
```

Get the lat/lng from [latlong.net](https://www.latlong.net/): search the
place name, copy the two numbers, paste them in. Posts without `location:`
simply don't get a pin — totally fine for "rest day" or "travel day"
posts where there's no specific spot to mark.

The map automatically draws a dashed line connecting the day pins in the
order you set with the `order:` field, so the route reflects however you
choose to sequence the days.

## Comments

Each post automatically gets a comments section at the bottom — provided
your husband has activated Cusdis (a one-time setup). Visitors don't need
to sign up; they just type a name and a message and hit submit.

To moderate (delete spam, hide rude messages), log in to your Cusdis
dashboard at [cusdis.com](https://cusdis.com/). It also emails when a new
comment lands.

## Filtering and sorting (for visitors)

This part isn't for writing posts — it's just so you know what visitors
see. The homepage and `/trips/` page now have:

- A **Sort** dropdown (Most recent / Oldest / By location / By name)
- **Tag filter chips** — clicking one shows only matching trips. Click
  multiple for an "any of these" view. The tags come from the `tags:`
  field on each trip in `_data/trips.yml`.

You manage the trip-level tags by editing that file. Pick whatever
categorization is useful — region (Europe, Asia), style (road-trip,
beach), theme (food, hiking, family). Lowercase + dashes is the convention.

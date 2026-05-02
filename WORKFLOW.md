# How to Post a New Travel Entry

This guide is the everyday "I just got back from the day, want to write it up" workflow.
Once your husband finishes the one-time setup, you only ever need this page.

You'll do **everything from a web browser**. No code editor, no terminal, no installs.

---

## The 5-minute version

1. Go to https://github.com/rojamich/travels
2. Open the `_posts/` folder
3. Click **Add file → Create new file**
4. Name the file using this exact pattern:
   ```
   2024-06-03-day-3-the-south-coast.md
   ```
   (date first, then a short description, no spaces, dashes between words, ends in `.md`)
5. Paste the **template below**, fill in your text, save (called "commit") at the bottom.
6. Within ~1 minute the new entry is live at https://rojamich.github.io/travels/

That's it.

---

## The template — copy and paste this for every new post

```markdown
---
title: "Day 3 — The South Coast"
date: 2024-06-03
categories:
  - iceland-2024
order: 3
header:
  teaser: /travels/assets/images/iceland-2024/day3-cover.jpg
  overlay_image: /travels/assets/images/iceland-2024/day3-cover.jpg
  overlay_filter: 0.4
tags:
  - iceland
  - waterfalls
gallery:
  - url: /travels/assets/images/iceland-2024/day3-photo1.jpg
    image_path: /travels/assets/images/iceland-2024/day3-photo1.jpg
    alt: "what this photo shows"
  - url: /travels/assets/images/iceland-2024/day3-photo2.jpg
    image_path: /travels/assets/images/iceland-2024/day3-photo2.jpg
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
| `gallery:` | One block per gallery photo. Add or remove blocks as needed. |
| `excerpt:` | One-sentence summary shown in listings |
| Body | Everything below the second `---`. This is your actual blog post. |

---

## Adding photos

### Step 1: compress them first

Phone photos are huge. Drag-and-drop them into one of these (free, no signup):

- [Squoosh.app](https://squoosh.app/) — best quality, more options
- [TinyPNG.com](https://tinypng.com/) — simpler, batch-uploads up to 20 at a time

Aim for **under 500 KB each** after compression.

### Step 2: upload to the right folder

1. On GitHub, go to `assets/images/iceland-2024/` (or whatever trip you're on).
2. Click **Add file → Upload files**.
3. Drag the compressed photos in.
4. Scroll down → **Commit changes**.

### Step 3: reference them in your post

The path is always:

```
/travels/assets/images/<trip-slug>/<filename>
```

So if you uploaded `sunset.jpg` to the iceland-2024 folder:

```
/travels/assets/images/iceland-2024/sunset.jpg
```

To put a photo inline in the post body:

```markdown
![A nice sunset](/travels/assets/images/iceland-2024/sunset.jpg)
```

To use it as the cover, put it in the `header:` block of the front matter.
To put it in the gallery, add it as a new entry under `gallery:`.

---

## Adding videos

YouTube and Vimeo are free and don't count toward GitHub's storage. Upload
the video to YouTube (you can mark it Unlisted if it's just for family),
then paste this snippet into the post wherever you want the video:

```html
<iframe width="100%" height="400"
  src="https://www.youtube.com/embed/VIDEO_ID_HERE"
  frameborder="0"
  allowfullscreen></iframe>
```

To get the `VIDEO_ID`: from a YouTube URL like
`https://www.youtube.com/watch?v=dQw4w9WgXcQ`, the ID is `dQw4w9WgXcQ`.

**Don't upload `.mp4` files into the repo** — videos are huge and will
quickly run you into GitHub's storage limits.

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

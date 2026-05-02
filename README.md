# Travel Blog — Setup Guide

This is a Jekyll-based travel blog that runs free on GitHub Pages.
Site URL once deployed: **https://rojamich.github.io/travels/**

This README is for **you (the technical setup person).**
For the day-to-day "how do I post a new entry" guide, see [WORKFLOW.md](WORKFLOW.md).

---

## What's in this folder

```
.
├── _config.yml             ← site-wide settings (title, theme, URL)
├── Gemfile                 ← Ruby gem list (read by GitHub Pages, not by you)
├── .gitignore              ← files Git should ignore
│
├── index.html              ← homepage (auto-lists trips)
│
├── _data/
│   ├── trips.yml           ← MASTER LIST of trips (edit this when adding a trip)
│   └── navigation.yml      ← top nav menu items
│
├── _pages/
│   ├── trips.md            ← "All Trips" page
│   ├── about.md            ← About page
│   └── iceland-2024.md     ← one file per trip; lists its posts
│
├── _posts/
│   ├── 2024-06-01-day-1-arrival-in-reykjavik.md
│   └── 2024-06-02-day-2-the-golden-circle.md
│
├── assets/
│   └── images/
│       └── iceland-2024/   ← photos for that trip live here
│
└── scripts/
    ├── import_blogger.py   ← convert Blogger XML export to Jekyll posts
    └── requirements.txt    ← Python deps for the import script
```

---

## One-time setup (about 15 minutes)

### 1. Create the GitHub repo

1. On GitHub, click **+ → New repository**.
2. Name it exactly: **`travels`**
3. Set it to **Public** (required for free GitHub Pages).
4. Do NOT initialize it with a README — we already have one.
5. Click **Create repository**.

### 2. Push this folder to GitHub

The simplest path is GitHub Desktop:

1. Install [GitHub Desktop](https://desktop.github.com/) if you don't have it.
2. **File → Add local repository →** select this folder.
3. It will say "this is not a Git repository" — click **Create a repository**.
4. **Publish repository** (top right). Make sure "Keep this code private" is **unchecked**.

Or via command line, from this folder:

```bash
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/rojamich/travels.git
git push -u origin main
```

### 3. Turn on GitHub Pages

1. On GitHub, go to your `travels` repo → **Settings → Pages**.
2. Under **Build and deployment → Source**, pick **Deploy from a branch**.
3. Branch: **main**, folder: **/ (root)**. Click **Save**.
4. Wait ~1 minute. The page will refresh and show:
   *Your site is live at https://rojamich.github.io/travels/*

That's it. The site builds automatically every time anything is pushed to `main`.

### 4. Verify it works

Open https://rojamich.github.io/travels/ in a browser. You should see:
- The homepage with a single Iceland 2024 card
- Clicking the card → trip page listing Day 1 and Day 2
- Clicking a day → the full post

The sample posts use `picsum.photos` placeholder images so it looks alive
out of the box. Replace those URLs (in the post front matter) with real
photos from `/assets/images/iceland-2024/` once you upload them.

---

## Adding photos

Drag-and-drop them into the GitHub web UI:

1. Go to your repo → `assets/images/iceland-2024/` (or whatever trip folder).
2. Click **Add file → Upload files**.
3. Drag photos in. **Commit changes**.

In a post, reference an image as:

```markdown
![Caption here](/travels/assets/images/iceland-2024/sunset.jpg)
```

Note the `/travels/` prefix — that's the `baseurl` from `_config.yml`.

### Compressing photos

Phone photos are typically 4–8 MB each. The repo will balloon fast.
**Before uploading, run them through:**

- [Squoosh.app](https://squoosh.app/) — drag-and-drop, browser-only
- [TinyPNG.com](https://tinypng.com/) — even simpler

Aim for **under 500 KB per photo**. The site loads way faster, and Google
Pages has a soft 1 GB repo limit.

---

## Importing existing Blogger posts

```bash
# in this folder
pip install -r scripts/requirements.txt
python scripts/import_blogger.py path/to/blog-export.xml --trip iceland-2024
```

That will:
- Convert each Blogger post to Markdown in `_posts/`
- Download all referenced images into `assets/images/iceland-2024/`
- Tag everything with the trip slug you provided

If the Blogger blog covers multiple trips, run the script multiple times
with `--since` and `--until` to bucket posts by date range, e.g.:

```bash
python scripts/import_blogger.py blog.xml --trip iceland-2024 --since 2024-06-01 --until 2024-06-14
python scripts/import_blogger.py blog.xml --trip japan-2025  --since 2025-03-10 --until 2025-03-24
```

After importing, open each generated `.md`, add an `order:` field to control
the sequence on the trip page, and clean up any messy formatting Blogger left behind.

---

## Adding a new trip

1. Add an entry to `_data/trips.yml` (copy the existing Iceland one).
2. Create `_pages/<slug>.md` (copy `iceland-2024.md`, change `permalink`,
   `title`, and `trip_slug`).
3. Create `assets/images/<slug>/` and add photos.
4. Write posts in `_posts/` with `categories: [<slug>]` and an `order:` field.

The homepage and `/trips/` page will pick up the new trip automatically.

---

## Comments (Cusdis — visitors don't need an account)

The post template already includes a comments section. It only renders once
you've added a Cusdis App ID to `_config.yml`.

1. Go to [cusdis.com](https://cusdis.com/) and sign up (free, generous limits).
2. Add a new site. URL: `https://rojamich.github.io/travels/`.
3. They give you an **App ID** that looks like a UUID (e.g. `8b3f1c2e-...`).
4. Open `_config.yml`, find this line:
   ```yaml
   cusdis_app_id: ""
   ```
   Paste the App ID between the quotes, commit, push.
5. Visitors can now comment on any post — they just type a name and message.
   You moderate from your Cusdis dashboard (approve/delete).

To temporarily turn off comments: clear `cusdis_app_id` back to `""`.

## Maps

There's a `/map/` page in the nav showing one pin per trip on a world map.
Click a pin → zoom in and reveal the day-by-day route for that trip.
Each trip page also has a small embedded map of just that trip.

To make a trip appear on the map, add `lat:` and `lng:` to its entry in
`_data/trips.yml`. To make individual days appear as pins on the route,
add `location:` to each post:

```yaml
location:
  name: "Reykjavik, Iceland"
  lat: 64.1466
  lng: -21.9426
```

Get coordinates from [latlong.net](https://www.latlong.net/) — search a
place and copy the lat/lng. Posts without `location:` simply don't get a pin.

**Optional v2 upgrade:** fill visited countries with their flag (instead
of just placing a pin). Doable but adds ~2 hours of work — needs country
boundary GeoJSON, flag images, and SVG pattern fills. The `country_code`
field already in `_data/trips.yml` is forward-compat for this — when you
want it, just say so.

## Subscriber emails (free)

Sign up for [follow.it](https://follow.it/), point it at the RSS feed at
`https://rojamich.github.io/travels/feed.xml`. They give you an embed snippet
(a small HTML form). Paste it into `_pages/about.md` where the comment
`<!-- Subscriber widget goes here once configured. -->` is.

That's the easiest free option. No domain, no server, no monthly cost.

---

## Optional upgrades (do these later)

| Want | Action |
|------|--------|
| Visual editor for your wife (no Markdown) | Switch hosting from GitHub Pages to Netlify (still free) and turn on Decap CMS. About 15 minutes of work. Ask Claude when you're ready. |
| Comments | Set up [Giscus](https://giscus.app/) and uncomment the `comments:` block in `_config.yml`. |
| Custom domain | Buy a domain ($10–15/yr), add a `CNAME` file with the domain, configure DNS. |
| Auto-compress photos | A pre-commit hook running ImageMagick or a GitHub Action with [calibreapp/image-actions](https://github.com/calibreapp/image-actions). |

---

## Troubleshooting

**Site broken after a push.** Go to repo → **Actions** tab. The latest
workflow run will show a red X if the build failed. Click in to see the
error — usually a typo in YAML front matter (a missing colon, mis-indented field).

**Photos look gigantic on the page.** They're not compressed. Run them
through Squoosh and re-upload.

**Page changes don't appear.** GitHub Pages caches aggressively. Hard
refresh (Ctrl+F5 / Cmd+Shift+R). If still nothing, check the Actions tab.

**Image broken on a post.** Three usual culprits:
- The path is missing the `/travels/` baseurl prefix
- Filename casing (`Photo.jpg` vs `photo.jpg`) — GitHub Pages is case-sensitive
- The file wasn't actually pushed (check the repo on github.com)

---

That's the whole thing. Hand [WORKFLOW.md](WORKFLOW.md) to your wife and she
should be able to post without ever opening this README.

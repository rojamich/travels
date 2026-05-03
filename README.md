# Travel Blog — Setup Guide

A Jekyll-based travel blog hosted on Netlify, with photos on Cloudinary and a
visual content editor (Decap CMS) at `/admin/`.

Live URL: **https://where-in-the-world-are-mike-and-jen.netlify.app**

This README is for **you (the technical setup person).**
For the day-to-day "how do I post a new entry" guide that you hand to your
wife, see [WORKFLOW.md](WORKFLOW.md).

---

## What's in this folder

```
.
├── _config.yml             ← site-wide settings (title, theme, URL, plugins)
├── Gemfile                 ← Ruby gem list (read by Netlify, not by you)
├── netlify.toml            ← Netlify build config
├── .gitignore
│
├── admin/                  ← Decap CMS visual editor (lives at /admin/)
│   ├── index.html          ← entry point — your wife visits this
│   └── config.yml          ← form definitions (which fields appear)
│
├── index.html              ← homepage (auto-lists trips)
│
├── _data/
│   ├── trips.yml           ← MASTER LIST of trips (you edit this)
│   └── navigation.yml      ← top nav menu items
│
├── _pages/
│   ├── trips.md            ← "All Trips" page
│   ├── about.md            ← About page
│   ├── map.md              ← interactive world map
│   └── iceland-2024.md     ← one file per trip; lists its posts
│
├── _posts/                 ← your wife's posts (she creates these via /admin/)
│   ├── 2024-06-01-day-1-arrival-in-reykjavik.md
│   └── 2024-06-02-day-2-the-golden-circle.md
│
├── _includes/
│   ├── head/custom.html    ← Google Fonts + Netlify Identity widget
│   ├── subscribe.html      ← email subscription block
│   ├── trip-map.html       ← embedded mini-map for trip pages
│   └── comments-providers/
│       └── custom.html     ← Cusdis comments embed
│
├── assets/
│   ├── css/main.scss       ← coastal palette + custom styles
│   ├── js/maps.js          ← Leaflet map logic
│   ├── js/sort-filter.js   ← homepage/trip-list sort + tag filter
│   └── images/             ← (rarely used now — photos live on Cloudinary)
│
└── scripts/
    ├── import_blogger.py   ← convert Blogger XML export to Jekyll posts
    └── requirements.txt
```

---

## One-time hosting setup

### 1. Netlify — connect to the GitHub repo

1. Sign in at [app.netlify.com](https://app.netlify.com).
2. **Add new site → Import an existing project → Deploy with GitHub**.
3. Pick the `rojamich/travels` repo.
4. Netlify will show a build settings page. Defaults are correct (build
   command `bundle exec jekyll build`, publish dir `_site`) — they come
   from the `netlify.toml` in the repo. Click **Deploy site**.
5. First build takes ~2-3 min. Once it's green, you'll have a temporary URL
   like `random-name.netlify.app`.
6. Go to **Site configuration → Change site name** and set it to:
   `where-in-the-world-are-mike-and-jen`
7. Confirm the live URL is `https://where-in-the-world-are-mike-and-jen.netlify.app`.

### 2. Netlify Identity — admin login

1. In your Netlify site dashboard, click **Integrations**, find
   **Netlify Identity**, click **Enable Identity** (free tier is fine).
2. Under **Registration preferences**, set to **Invite only** (so randos
   can't sign themselves up as editors).
3. Under **Services → Git Gateway**, click **Enable Git Gateway**. This
   lets the CMS commit to the repo on your wife's behalf.
4. Under **Identity → Users**, click **Invite users** and enter your
   wife's email: `jennabooksrojas@gmail.com`. She'll get an email with
   a link.
5. When she clicks it, she'll land on the homepage with a token in the URL,
   the page detects it, prompts her to set a password, and forwards her
   to `/admin/`. She's in.

### 3. Cloudinary — already configured

The Cloudinary cloud name and API key are already in `admin/config.yml`.
Photos uploaded inside `/admin/` will automatically go to your Cloudinary
account. Visit your [Cloudinary dashboard](https://console.cloudinary.com/)
to see them landing as she works.

### 4. Turn off GitHub Pages (optional but recommended)

Once Netlify is up and working, the old GitHub Pages site at
`rojamich.github.io/travels/` will be serving a broken version of the same
content. Turn it off so there's only one canonical site:

1. GitHub repo → **Settings → Pages**.
2. Under **Source**, change to **None** (or **Deploy from a branch** with a
   non-existent branch). Save.

---

## Daily workflow

**Your wife** uses the visual editor:
- She goes to `/admin/`, logs in, and creates/edits posts via forms.
- Photos go to Cloudinary automatically — no compression, no folder management.
- "Publish" commits to GitHub via Netlify Git Gateway, which triggers a rebuild.

**You** continue to use VS Code + GitHub for everything that's not a post:
- Theme/CSS tweaks (`assets/css/main.scss`)
- Trip metadata (`_data/trips.yml`)
- New trip pages (`_pages/<slug>.md`)
- Site config (`_config.yml`)
- The admin form schema if it ever needs new fields (`admin/config.yml`)

Pushing to `main` → Netlify auto-rebuilds within a minute.

---

## Adding a new trip

The CMS doesn't manage trips, only posts. To add a new trip:

1. Add an entry to `_data/trips.yml` (copy the Iceland one). Required fields:
   `slug`, `name`, `description`, `cover`, `start_date`, `end_date`,
   `location`, optionally `lat`/`lng` (for the world map pin),
   `country_code`, and `tags`.
2. Create `_pages/<slug>.md` by copying `_pages/iceland-2024.md` and
   changing `permalink`, `title`, and `trip_slug` to match the new slug.
3. **Add the trip to the dropdown in the admin form**: open
   `admin/config.yml`, find the `categories` field, add a new option:
   ```yaml
   options:
     - { label: "Iceland 2024", value: "iceland-2024" }
     - { label: "Japan 2025", value: "japan-2025" }
   ```
   Without this step, your wife can't pick the new trip from the form.
4. Push. Done.

---

## Comments — Cusdis

Already set up. The Cusdis App ID is in `_config.yml` (`cusdis_app_id`).
Visitors comment without an account; you moderate at
[cusdis.com](https://cusdis.com/dashboard).

To temporarily disable comments: clear `cusdis_app_id` back to `""`.

---

## Maps

`/map/` page shows one pin per trip on a world map. Click a pin → zoom in
and reveal the day-by-day route for that trip. Each trip page also embeds
a smaller map of just that trip.

For trips: add `lat:` and `lng:` to the entry in `_data/trips.yml`.
For per-day pins: when your wife adds a `Map pin location` in the admin
form, that day shows up as a pin on the route. Get coordinates from
[latlong.net](https://www.latlong.net/).

**Optional v2 upgrade:** fill visited countries with their flag (instead
of just a pin). Adds ~2 hours of work — needs country boundary GeoJSON,
flag images, and SVG pattern fills. The `country_code` field in
`_data/trips.yml` is forward-compat for this — say the word when you
want it.

---

## Importing existing Blogger posts

```bash
pip install -r scripts/requirements.txt
python scripts/import_blogger.py path/to/blog-export.xml --trip iceland-2024
```

Converts each post to Markdown in `_posts/` and downloads images to
`assets/images/<trip>/`. After importing, you may want to:
- Open each generated `.md` and set the `order:` field to control sequence
- Move the downloaded images to Cloudinary so they live alongside new uploads
  (or leave them in the repo — both work)

If the Blogger blog covers multiple trips, run the script multiple times
with `--since` and `--until` to bucket posts by date range.

---

## Subscriber emails (free)

Sign up for [follow.it](https://follow.it/), point it at the RSS feed:
`https://where-in-the-world-are-mike-and-jen.netlify.app/feed.xml`.
They give you an HTML form snippet — paste it into
`_includes/subscribe.html` between the `<!-- SUBSCRIBE-FORM START -->`
and `<!-- SUBSCRIBE-FORM END -->` markers, replacing the placeholder.

---

## Optional upgrades

| Want | How |
|------|-----|
| Custom domain (e.g. `ourtravels.com`) | Buy at Namecheap/Cloudflare (~$12/yr). Netlify → Domain settings → Add custom domain. SSL is free and automatic. |
| Country flag fill on world map | Mentioned in Maps section above. Ask Claude. |
| Auto-resize photos beyond Cloudinary defaults | Cloudinary has powerful URL-based transformations. Can be set as defaults in the upload preset. |
| Multi-user editor (e.g. you and wife both editing) | Netlify Identity → invite more users. Decap respects auth. |

---

## Troubleshooting

**Site broken after a push.** Go to Netlify dashboard → **Deploys** tab.
The failing deploy will show a red X. Click in for the build log;
errors are at the bottom.

**Wife can't log in to /admin/.**
- Netlify Identity might not be enabled (check site settings).
- Git Gateway might not be enabled (check site settings).
- Her invitation may have expired (24h limit) — re-invite.

**Wife logs in but sees "config not found" or no posts.**
- The `admin/config.yml` file isn't being served. Check that the file
  exists at the repo root and that Netlify deployed the latest commit.

**Photos upload but don't appear.**
- Check the post's front matter — the image URL should look like
  `https://res.cloudinary.com/dgw35sldo/image/upload/...`.
- If it does, check that the URL works in a fresh browser tab (rare network/CORS issue).

**Comment section missing.**
- `cusdis_app_id` is empty in `_config.yml`.
- Or the Cusdis Site ID doesn't match what's configured.

**Image broken on an old (pre-migration) post.**
- These referenced `/travels/...` paths. Now baseurl is empty, so the
  image path should just be `/...`. Edit the post via /admin/ and re-upload
  the photo, or fix the path manually in the file.

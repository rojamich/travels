# Travel Blog — Setup Guide

A Jekyll-based travel blog hosted on Netlify, with photos on Cloudinary and a
visual content editor (Decap CMS) at `/admin/`.

Live URL: **https://where-in-the-world-are-mike-and-jen.netlify.app**

This README is for **you (the technical setup person).**
For the day-to-day "how do I post a new entry" guide that you hand to your
wife, see [WORKFLOW.md](WORKFLOW.md).
For changing files yourself — commit, push, why a change hasn't appeared yet —
see [EDITING.md](EDITING.md).

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
│   └── navigation.yml      ← top nav menu items
│
├── _trips/                 ← one file per trip (managed via /admin/)
│   └── iceland-2024.md
│
├── _layouts/
│   └── trip.html           ← layout for trip pages (cover, map, day list)
│
├── _pages/
│   ├── trips.md            ← "All Trips" page
│   ├── about.md            ← About page
│   └── map.md              ← interactive world map
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
    ├── audit_cloudinary_orphans.py  ← find/delete unused photos on Cloudinary
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
- Trip metadata (one file per trip in `_trips/`)
- New trip pages (`_pages/<slug>.md`)
- Site config (`_config.yml`)
- The admin form schema if it ever needs new fields (`admin/config.yml`)

Pushing to `main` → Netlify auto-rebuilds within a minute.

---

## Adding a new trip

**Your wife does this herself in `/admin/`** — no code changes needed:

1. She goes to `/admin/`, clicks **"New Trip"** in the trips collection.
2. Fills in the form (Trip name, dates, cover photo, location, lat/lng for the map pin, tags).
3. Clicks **Publish**.
4. Within a minute, the new trip appears on the homepage, /trips/, and the world map. It also auto-populates the **Trip** dropdown when she creates posts — no separate config to update.

Each trip is stored as one file in `_trips/<slug>.md`. The trip page lives at `/<slug>/`.

If you ever need to edit a trip directly (rare — for advanced things the form doesn't expose), the file format is the same fields as the form, plus optional markdown body for an intro paragraph.

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

For trips: add `lat:` and `lng:` to the trip's file in `_trips/`.
For per-day pins: when your wife adds a `Map pin location` in the admin
form, that day shows up as a pin on the route. Get coordinates from
[latlong.net](https://www.latlong.net/). A place that has been pinned once
is remembered in `_data/places.yml` and filled in automatically the next
time it is named.

Country shading is on `/stats/`, drawn from a vendored copy of the world
boundaries in `assets/data/` rather than a CDN.

**Which map the pins sit on** is a setting, in `_config.yml` under `map:`:

```yaml
map:
  provider: "carto"    # esri | carto | osm
  carto_key: ""        # free key from https://carto.com/basemaps/apikey/
```

This exists because CARTO — free and key-free for years — began stamping
`API KEY REQUIRED` across unkeyed tiles in 2026. A key is free and instant,
and if `provider` is `carto` while `carto_key` is empty, the maps fall back
to Esri rather than showing the watermark. `esri` needs no key at all and
labels places in English worldwide; `osm` is the last resort, because it
labels everything in the local script.

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

## What needs a human

Almost nothing on this site can quietly go out of date. The country counts,
the nights, the continents, the maps, the leaderboard placings, the medal
table, the search index, the editor's tag and country pickers — all computed
from the posts and trips on every build. Get one wrong and it is wrong
loudly, on `/admin-stats/`, with the trip that caused it named.

A short list of things is typed by hand instead, and those are the ones that
rot. They look no different when they are stale:

| File | Feeds | How it goes wrong |
| ---- | ----- | ----------------- |
| `_data/status.yml` | the "where we are now" bar on every page, the days-on-the-road clock | you move and it still says the last place |
| `_data/records.yml` | personal bests on `/stats/` | a row with no value never appears — 8 of 11 are blank today |
| `_data/country_images.yml` | flags beside country names on `/stats/` | a new country has no flag; a typo'd name never matches |
| `_data/us_state_images.yml` | the same for US states | as above |
| `_data/favorites.yml`, `_data/lessons.yml` | `/favorites/`, `/lessons/` | nothing prompts you to add to them |
| `_data/places.yml` | remembered coordinates | a place pinned wrong once is remembered wrong |

**The reminder lives on [`/admin-stats/`](https://where-in-the-world-are-mike-and-jen.netlify.app/admin-stats/),
in the "Needs a human" panel at the top**, and the editor shows the count as a
small banner once per session so it reaches her without her going looking. It
is worked out fresh on every build from the same data the site renders, so it
cannot itself fall behind, and it stays quiet when there is nothing to say.
The dates it quotes come from git (`_plugins/data_freshness.rb`) rather than
the files' timestamps, because a build server clones the repo fresh and every
file looks new.

`/admin-stats/` asks for the same Netlify Identity login as `/admin/` — log
into one and you are in both. Be clear-eyed about what that gate is: it runs
in the browser, so it hides the page from visitors and search engines but
does not stop someone who knows the URL from fetching the raw HTML. Netlify
can only check a login *before* serving a file on a Business plan. So nothing
secret goes on that page — view counts and housekeeping notes only. The
count the editor reads (`/admin-upkeep.json`) is deliberately just a number
for the same reason; the detail stays behind the login.

If something genuinely private ever needs to live there, the fix that works
on this plan is to stop building it into a static file: serve it from a
Netlify Function that verifies the Identity token against
`/.netlify/identity/user`, and have the page fetch it after login.

To add a check: work it out in Liquid at the top of `_pages/admin-stats.html`,
push a sentence onto `upkeep`, and it renders itself. Don't add one that
needs its own copy of something the site already knows — a reminder that
drifts is worse than no reminder.

### The parts no build can check

These need a person to look, once in a while. Nothing in the repo can see
them:

- **Cloudinary storage.** The free tier is effectively full. `python
  scripts/audit_cloudinary_orphans.py` lists images no post references.
- **The CARTO key** in `_config.yml`, if you're using CARTO — a revoked or
  expired key brings the watermark back. The maps fall back to Esri if the
  key is blank, but not if it is present and rejected.
- **Netlify Identity registration.** It must stay *Invite only*; open
  registration means anyone who signs up can edit the site through Git
  Gateway. Netlify dashboard → Identity → Registration.
- **Pinned front-end versions.** Leaflet and GLightbox are pinned with
  integrity hashes (`_includes/map-libs.html`, `_includes/head/custom.html`).
  They are safe as they are, and upgrading means changing the version and
  the hash together — see the comments in those files.
- **The flags on `/stats/`** are hotlinked from Wikimedia, which asks that
  people not hotlink. They work today; if they ever stop, that is why.

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

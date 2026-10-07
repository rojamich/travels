# Making changes yourself

For when *you* want to change a file — a layout tweak, a typo in a post, a
setting — rather than having Jen do it through the editor at `/admin/`.

- She writes posts in the editor: **[WORKFLOW.md](WORKFLOW.md)**
- One-time hosting setup lives in: **[README.md](README.md)**

---

## The one thing to understand first

Saving a file on your laptop changes **nothing**. The website is built from
what is stored on GitHub, so a change only becomes real once it has made all
four hops:

```
save the file  →  commit it  →  push it to GitHub  →  Netlify rebuilds  →  live
```

Miss any one of those and the site looks exactly as it did before. Most
"I changed it but nothing happened" moments are a change that stopped at
step 1 or 2.

The rebuild is not instant. Netlify takes roughly **2–5 minutes** to build this
site (there are ~300 posts), so give it a few minutes before deciding something
is wrong.

---

## Option A — edit on GitHub.com (easiest, nothing to install)

Best for a quick typo fix. This is the path that produced the
"Update ...midnight-train....md" commit, and it worked fine.

1. Go to <https://github.com/rojamich/travels>.
2. Click your way to the file (posts are under `_posts/`).
3. Click the **pencil** icon, top right of the file.
4. Make the change.
5. Click **Commit changes…**, then **Commit changes** again in the dialog.
   Leave "Commit directly to the `main` branch" selected.
6. Wait a few minutes, then hard-refresh the page (see below).

There is no separate "push" — committing on GitHub.com *is* the push.

---

## Option B — edit locally in VS Code

Best when you're changing more than one file, or something structural.

### Every single time, in this order

**1. Get the latest first.** Jen's published posts arrive as commits you don't
have yet. If you skip this, your push gets rejected or you end up merging by
hand. In VS Code's terminal, from the project folder:

```bash
git pull
```

**2. Edit and save your files** as normal in VS Code.

**3. See what you actually changed:**

```bash
git status
```

Anything listed in red is changed-but-not-committed. If this comes back
"nothing to commit, working tree clean", you have no changes to publish — that
alone explains a change that never appeared.

**4. Commit the changes.** This is the step that's easy to forget; `Ctrl+S` is
not a commit:

```bash
git add -A
```

```bash
git commit -m "Short description of what you changed"
```

**5. Push to GitHub:**

```bash
git push
```

Read the output. `Everything up-to-date` means there was nothing to send — go
back to step 3. If it complains about being *rejected* or *behind*, run
`git pull` and then `git push` again.

**6. Confirm it landed.** This should print just the branch name, with no
"ahead" count after it:

```bash
git status -sb
```

If it says `ahead 1` (or more), the commit is still sitting on your laptop —
push it.

### VS Code's buttons do the same thing

Source Control panel (the branch icon in the left bar): type a message in the
box → **Commit** → **Sync Changes**. "Sync" is pull and push together. If it
asks "always commit all changes?", say yes.

---

## "I pushed it and the site didn't change"

Work down this list; it's in order of how often each one is the answer.

1. **Give it 5 minutes.** The build has to finish first.
2. **Hard-refresh the page:** `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac).
   A normal refresh will happily show you the version already sitting in your
   browser's cache. On a phone, try a private/incognito tab.
3. **Check the commit is really on GitHub.** Open
   <https://github.com/rojamich/travels/commits/main> — your change should be at
   the top of that list. If it isn't, it never left your laptop: `git status`,
   then commit and push.
4. **Check the build.** Netlify dashboard → your site → **Deploys**.
   - Green "Published" with a recent timestamp = it built and shipped. If the
     page still looks old after that, it's caching (step 2).
   - Red "Failed" = the build broke; click it and read the bottom of the log.
     The site keeps serving the last good version until it's fixed.
   - Nothing new listed at all = Netlify never saw the push. Check
     Site configuration → Build & deploy: the repo is still connected and
     builds aren't paused.
5. **Check you edited the file the page actually uses.** The homepage is
   `index.html`, a post is its file in `_posts/`, site-wide settings are
   `_config.yml`. Changing `README.md`, or anything in `scripts/`, changes
   nothing visible.
6. **Check you're on `main`.** `git branch --show-current` should print `main`.
   A commit on any other branch is invisible to the site until it's merged.

---

## Two rules that avoid the nasty cases

**Pull before you start, always.** Your copy of the project goes stale as soon
as Jen publishes anything. (It was 6 commits behind when we looked at it — no
harm done, but that's the state where a push gets rejected and it feels like Git
is fighting you.)

**Don't hand-edit a post she has open as a draft.** A draft in the editor lives
on its own branch until she hits Publish; when she does, that branch's version of
the file wins and your edit is quietly overwritten. Check
<https://github.com/rojamich/travels/pulls> first — an open pull request named
`Add post: <slug>` or `Edit post: <slug>` means that post is currently a draft.
Either wait until she publishes it, or make the change for her inside `/admin/`.

---

## Where things live

| You want to change | Edit this |
|---|---|
| A post's text | `_posts/<date>-<slug>.md` |
| A trip's name, dates, cover photo, map pin | `_trips/<slug>.md` |
| The homepage | `index.html` |
| Site title, URL, plugins, defaults | `_config.yml` |
| A standalone page (About, Map, Search…) | `_pages/` |
| The look — colours, spacing, fonts | `assets/css/` |
| The form Jen fills in at `/admin/` | `admin/config.yml` |
| The editor page itself (login, safety net) | `admin/index.html` |
| Build-time logic (stats, galleries, tags) | `_plugins/*.rb` |

---

## Things that look like errors but aren't

**`search-index.json` shows "Expected a JSON object, array or literal".**
That file isn't JSON — it's a Jekyll *template* that produces JSON when the site
builds, which is why it starts with `---` and Liquid tags. VS Code checks it as
JSON and complains about line 1. Nothing is broken. `.vscode/settings.json` now
tells VS Code to treat that file (and `manifest.json`, same story) as plain text,
so the red squiggle is gone. If it ever comes back, that settings file is missing
or the filename changed.

**Every save builds a preview of the whole site, and it's free.** Netlify
charges 15 credits for a production deploy and nothing for a deploy preview,
so checking a post costs nothing and publishing it costs. The link appears on
the post's card in the **Workflow** tab once the build finishes — a minute or
so after saving. It is the real site, built the real way, so what it shows is
what you'll get.

This used to be turned off, back when the plan was billed in build minutes
and previews spent them. Under credits that reasoning is backwards. If you
ever find deploy previews disabled in the Netlify dashboard, that's a
regression, not a saving.

---

## Save and Publish are not the same thing

This is the one thing worth knowing, because getting it wrong is how a
finished post goes live as an old draft.

- **Save** writes what is on screen to the post's branch on GitHub.
- **Publish** merges that branch. **It does not save first.**

So if a save fails and she presses Publish anyway, Publish works perfectly
and ships *the previous version*. Nothing reports a problem, because from
Publish's point of view nothing went wrong. That is what happened on
2026-09-03: a save was refused, the branch kept the older draft, and the
pull request that got merged was that older draft.

The editor now guards against this on its own:

- The pill at the bottom-left says whether GitHub actually has what is on
  screen: **✓ On GitHub**, **✏️ Unsaved**, or a red **⛔ NOT on GitHub**.
- A refused save puts a red bar across the top and leaves it there.
- Clicking **Publish** or **Set status** while the screen is ahead of
  GitHub is blocked, with an explanation. (There is a "Publish anyway"
  button if it is ever wrong.)

If she is unsure, the rule is: **press Save, wait for the pill to say
✓ On GitHub, then publish.**

---

## Getting her work back if a save is lost

The editor keeps a copy of the post every few seconds in her browser's local
storage: up to 30 versions per post, at least 8 even when space is short.
Since 2026-10-07 each version also holds the post **exactly as Decap had
it**: every field, and the body as markdown with its galleries, photo links
and YouTube links in it.

**First: don't reload, and don't start a new post.** Every unsaved new post
shares one history, so typing in a fresh one pushes old versions out. If a
save has just failed, click in the body, Ctrl+A, Ctrl+C, and paste it into
Notepad before doing anything else.

**Then use 🛟 Recover a draft**, the button at the bottom-left of `/admin/`.
It lists every post this browser has kept, with each version's time and size.
The newest version is often the damage (a blank page after a reload), so look
for the ★ longest one from around when she was writing.

- **Copy body**: paste it back by opening the post, switching the Body box to
  *Markdown* (top right of the box), selecting everything and pasting.
- **Download**: the whole post as a `.md` file, front matter and all, the same
  shape as the files in `_posts/`.
- Versions marked **"text only"** are from before 2026-10-07 and were saved
  from the screen: every word is there, but photos, the trip and the YouTube
  link are not. Each 👉 line marks something to re-add.
- **Download everything**, at the bottom, saves all the backups plus the
  editor's log as one file. Send that one when something has gone wrong.

The panel only reads. It never changes the post on screen.

Console commands (F12 → Console), if the button is ever not there:

| Command | What it does |
| --- | --- |
| `RECOVERY()` | Opens the same panel |
| `RECOVERY_LIST()` | Lists every version kept, with its time and size |
| `RECOVERY_FORM(N)` | Prints version N field by field (Chrome cuts long text short, so use the panel for the full thing) |
| `RECOVERY_FORM_COPY(N)` | Copies version N to the clipboard, in full |
| `ADMIN_LOG()` | Prints the editor's log, which survives a reload |

`RECOVERY_HISTORY()` and `RECOVERY_COPY(N)` are old names. This file kept
listing them after the commands themselves were removed, which is how she
ended up with errors on 2026-10-07. They work again now, as aliases.

Snapshots live in **that browser on that machine** and are kept 14 days. If
she wrote on her laptop, they are not on your phone.

**Why the token error happened** is in the editor log. The console clears
when the page reloads, but the log doesn't: it keeps the last 300 warnings,
errors and save events. Get it with `ADMIN_LOG()` or with **Download
everything**.

---

## Why the token errors happened at all

The login library Netlify ships (`gotrue-js`) throws the whole session away
whenever a token renewal fails — and it counts a dropped wifi connection or
a sleeping laptop as a failure, not just a genuinely expired login. So she
would be quietly signed out mid-sentence, with the editor still looking
completely normal, and only find out twenty minutes later when Save had no
token to send.

The editor now handles this in two stages.

**First, it tries not to lose the session at all.** Before renewing, it
keeps a copy of the login. If the renewal fails because the request never
reached the server — dropped wifi, a laptop waking up, switching networks —
the refresh token was never actually used, so the copy goes straight back
and she never knows anything happened. Her logs from 4 September show
exactly this case: her wifi changed, one request died with
`ERR_CONNECTION_CLOSED`, and that alone signed her out.

**Second, if the login genuinely is gone**, it says so within 15 seconds
rather than twenty minutes later at Save: the **"Your session has expired"**
box, with her draft snapshotted first and left untouched on screen. Signing
back in and pressing Save picks up where she was. Dismissing that box now
buys five minutes of quiet instead of having it reappear immediately.

It also renews far less often. Renewals triggered by clicking back into the
tab are capped at one every two minutes, since every renewal is another
chance for a flaky connection to drop mid-request. Saving and genuine
expiry are never held back.

---

## When Jen gets "failed to persist entry" in the editor

Sometimes her work is still on GitHub even though the editor said the save
failed — the text can make it there before the error appears. Check first,
before anything else:

1. Look at <https://github.com/rojamich/travels/pulls>. A pull request named
   `Add post: <slug>` / `Edit post: <slug>` holds what she typed — click
   **Files changed** to read it.
2. In the editor, the **Workflow** tab (top of the screen) lists drafts. If the
   post is there, tell her to open it *from that tab* and carry on. Starting
   again from "New Post" is what triggers the error loop: the CMS tries to create
   a draft branch that already exists, GitHub refuses it, and every save after
   that fails the same way.
3. If the post is missing from the Workflow tab but a branch for it exists at
   <https://github.com/rojamich/travels/branches>, that leftover branch is the
   blocker — delete it there and the next save works.
   `.github/workflows/cms-branch-cleanup.yml` now clears those away
   automatically, so this should stop happening on its own.
4. If the pull request exists but holds an **older** version than what she
   wrote, GitHub never received the last save. Do not merge it. Get her
   words back with **🛟 Recover a draft** (see above), then paste them into
   the editor and save properly.

---

## The two automated jobs (so they're not a surprise)

Both live in `.github/workflows/` and run on GitHub, not on your laptop.

- **Clean up CMS branches** — deletes a draft's branch when its pull request
  closes, and sweeps up any leftover `cms…` branch that has no open pull request
  and hasn't been touched in two days. This is what stops the save errors above
  from recurring.
- **Sync trip filters** — when a trip is added or renamed in `_trips/`, it
  regenerates the trip filter buttons in `admin/config.yml` and commits the
  result. You can also run it yourself:

```bash
python scripts/sync_trip_filters.py
```

#!/usr/bin/env python3
"""
reimport_lowres_blogger_images.py — replace the thumbnails the import brought over
=============================================================================
WHAT WENT WRONG
    Blogger embeds a resized copy of each photo in the post HTML, and the URL
    says which size: it ends in `=s320`. migrate_blogger_images.py fetched the
    URLs it found, so for 233 of the 6,052 images what landed in Cloudinary is
    a 320px thumbnail rather than the photo.

    Nothing about that is visible until the image is asked to be big. A 320px
    file looks fine in the body of a post and falls apart stretched across a
    banner, which is exactly how it was noticed.

WHY NOTHING NEEDS RE-UPLOADING BY HAND
    Blogger still has the originals, at the same URL with a different suffix:

        ...=s320   320x213      23 KB   <- what we imported
        ...=s1600  1600x1067   269 KB
        ...=s0     4845x3231   2.6 MB   <- the untouched original

    And .audit/blogger_to_cloudinary.json records which Blogger URL every
    Cloudinary asset came from. So this script re-fetches at a decent size and
    uploads over THE SAME public_id. Every URL already written into every post
    keeps working and quietly gets sharper. No edits to any post, no work in
    the editor.

STORAGE
    The account is near its limit, so this is deliberately not "fetch the
    original". Each image is re-fetched at --width (default 1600) and stored
    with an incoming transformation capping it there, the same way the original
    migration capped at 2400. Overwriting the same public_id replaces the file
    rather than adding one; the thumbnails are ~23 KB each and their
    replacements average ~475 KB as fetched, so the full 233 pull down roughly
    110 MB. What actually gets STORED is less: the incoming transformation
    re-encodes at quality auto:good on the way in. Run the plan first — it
    prints the total before anything is uploaded — and check the headroom on
    the Cloudinary dashboard, because this account has little.

    --width 1200 roughly halves it and still matches what the site delivers
    today; 1600 leaves room to raise the banner width later without doing this
    twice.

    Cloudinary regenerates derived images after an overwrite, so give it a few
    minutes before judging the result — and note the derivatives count toward
    storage too.

SAFETY
    - Prints a plan and writes NOTHING unless you pass --apply. (The sibling
      script shrink_cloudinary_assets.py has it the other way round — it acts
      unless you pass --dry-run. This one uploads over existing assets, so it
      defaults to the cautious direction.)
    - Skips anything already stored at a decent size, so a second run is a
      no-op rather than a re-upload.
    - Skips anything Blogger will not hand back bigger than what is already
      there, and lists it at the end as needing a real re-upload.
    - Resumable: every completed image is recorded in
      .audit/reimport_progress.json.
    - Never edits a post. The public_id does not change, so nothing needs to.

CREDENTIALS
    Needs the Cloudinary secret, the same as the other scripts here:

        PowerShell:
            $env:CLOUDINARY_URL = "cloudinary://<api_key>:<api_secret>@dgw35sldo"
        bash:
            export CLOUDINARY_URL="cloudinary://<api_key>:<api_secret>@dgw35sldo"

    Only needed for --apply. The plan runs without it.

USAGE
    python scripts/reimport_lowres_blogger_images.py                   # plan
    python scripts/reimport_lowres_blogger_images.py --limit 5 --apply # a taste
    python scripts/reimport_lowres_blogger_images.py --apply           # all of it

Exit codes: 0 = finished (or nothing to do), 1 = stopped without finishing.
"""

import argparse
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(ROOT, ".audit")
MAPPING_FILE = os.path.join(AUDIT_DIR, "blogger_to_cloudinary.json")
PROGRESS_FILE = os.path.join(AUDIT_DIR, "reimport_progress.json")
CONTENT_DIRS = (os.path.join(ROOT, "_posts"), os.path.join(ROOT, "_trips"))

DEFAULT_WIDTH = 1600
DEFAULT_THUMB_MAX = 640          # a source URL asking for this or less was a thumbnail
GOOD_ENOUGH = 1000               # already this wide in Cloudinary: leave it alone
USER_AGENT = "Mozilla/5.0 (travel-blog reimport script)"

PUBLIC_ID_RE = re.compile(r"/(blogger-import/[A-Za-z0-9_-]+)\.[A-Za-z0-9]+")
SIZE_SUFFIX_RE = re.compile(r"=s\d+(-[a-z0-9]+)*$")


# ---------------------------------------------------------------------------
# Reading image dimensions without a third-party imaging library
# ---------------------------------------------------------------------------
def image_size(data):
    """(width, height) from the first bytes of a JPEG or PNG, else (None, None)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height

    if data[:2] == b"\xff\xd8":                       # JPEG: walk the segments
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[i + 5:i + 9])
                return width, height
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    return None, None


def fetch(url, byte_range=None, timeout=30):
    """Returns (bytes, None) or (None, reason)."""
    headers = {"User-Agent": USER_AGENT, "Accept": "image/*"}
    if byte_range:
        headers["Range"] = "bytes=0-%d" % byte_range
    try:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), None
    except urllib.error.HTTPError as exc:
        return None, "HTTP %s" % exc.code
    except Exception as exc:                          # noqa: BLE001 - report anything
        return None, type(exc).__name__


def stored_size(cloudinary_url):
    """How big the asset actually is in Cloudinary, transformations stripped."""
    raw = re.sub(r"/image/upload/[^/]*?/v(\d+)/", r"/image/upload/v\1/", cloudinary_url)
    data, problem = fetch(raw, byte_range=65535)
    if problem:
        return None, None, problem
    width, height = image_size(data)
    return width, height, None if width else "unreadable image"


def blogger_url_at(source_url, size):
    """The same Blogger URL asking for a different size."""
    if SIZE_SUFFIX_RE.search(source_url):
        return SIZE_SUFFIX_RE.sub("=s%d" % size, source_url)
    return "%s=s%d" % (source_url, size)


# ---------------------------------------------------------------------------
# Which assets are candidates
# ---------------------------------------------------------------------------
def public_id_of(cloudinary_url):
    found = PUBLIC_ID_RE.search(cloudinary_url)
    return found.group(1) if found else None


def assets_in_use():
    """public_ids referenced by a post or trip today."""
    used = set()
    for directory in CONTENT_DIRS:
        if not os.path.isdir(directory):
            continue
        for name in os.listdir(directory):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(directory, name), encoding="utf-8") as handle:
                text = handle.read()
            for found in re.finditer(r"/(blogger-import/[A-Za-z0-9_-]+)\.", text):
                used.add(found.group(1))
    return used


def candidates(mapping, thumb_max, only_used):
    used = assets_in_use() if only_used else None
    out = []
    for source_url, cloudinary_url in mapping.items():
        size_match = re.search(r"=s(\d+)", source_url)
        if not size_match or int(size_match.group(1)) > thumb_max:
            continue
        public_id = public_id_of(cloudinary_url)
        if not public_id:
            continue
        if used is not None and public_id not in used:
            continue
        out.append({"public_id": public_id, "source": source_url,
                    "cloudinary": cloudinary_url,
                    "imported_at": int(size_match.group(1))})
    out.sort(key=lambda item: item["public_id"])
    return out


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            print("progress file unreadable — starting fresh")
    return {}


def save_progress(progress):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as handle:
        json.dump(progress, handle, indent=1, sort_keys=True)


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Replace Blogger thumbnails with the real photos, in place.")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH,
                        help="size to re-fetch and store at (default %d)" % DEFAULT_WIDTH)
    parser.add_argument("--thumb-max", type=int, default=DEFAULT_THUMB_MAX,
                        help="a source URL asking for this or fewer pixels was a "
                             "thumbnail (default %d)" % DEFAULT_THUMB_MAX)
    parser.add_argument("--good-enough", type=int, default=GOOD_ENOUGH,
                        help="leave alone anything already this wide in Cloudinary "
                             "(default %d)" % GOOD_ENOUGH)
    parser.add_argument("--limit", type=int, help="stop after this many images")
    parser.add_argument("--include-unused", action="store_true",
                        help="also fix assets no post references any more")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="seconds between uploads (default 0.2)")
    parser.add_argument("--apply", action="store_true",
                        help="actually upload. Without this, prints the plan only.")
    args = parser.parse_args()

    if not os.path.exists(MAPPING_FILE):
        print("Cannot find %s — that file records which Blogger URL each image "
              "came from, and without it there is nothing to re-fetch." % MAPPING_FILE)
        return 1

    with open(MAPPING_FILE, encoding="utf-8") as handle:
        mapping = json.load(handle)

    if args.apply and not os.environ.get("CLOUDINARY_URL"):
        print("CLOUDINARY_URL is not set — see the CREDENTIALS section at the top "
              "of this file. Nothing was uploaded.")
        return 1

    uploader = None
    if args.apply:
        try:
            import cloudinary
            import cloudinary.uploader
            cloudinary.config(secure=True)
            uploader = cloudinary.uploader
        except ImportError:
            print("The cloudinary package is missing: "
                  "pip install -r scripts/requirements.txt")
            return 1

    progress = load_progress()
    plan = candidates(mapping, args.thumb_max, not args.include_unused)
    todo = [item for item in plan if item["public_id"] not in progress]

    print("%d image(s) were imported from a thumbnail URL%s." %
          (len(plan), "" if args.include_unused else " and are still used by a post"))
    if len(todo) != len(plan):
        print("%d already done in an earlier run." % (len(plan) - len(todo)))
    if args.limit:
        todo = todo[:args.limit]
        print("limited to %d this run." % len(todo))
    if not todo:
        print("Nothing to do.")
        return 0
    print("Re-fetching at %dpx wide.%s\n" %
          (args.width, "" if args.apply else "  (plan only — pass --apply to upload)"))

    done = skipped = failed = 0
    uploaded_bytes = 0
    needs_human = []

    for index, item in enumerate(todo, start=1):
        public_id = item["public_id"]
        label = public_id.replace("blogger-import/", "")
        position = "[%d/%d]" % (index, len(todo))

        have_w, have_h, problem = stored_size(item["cloudinary"])
        if problem:
            print("  %s %s  cannot read what is stored (%s) — skipped" %
                  (position, label, problem), flush=True)
            failed += 1
            continue
        if have_w >= args.good_enough:
            print("  %s %s  %dx%d already fine — skipped" %
                  (position, label, have_w, have_h), flush=True)
            skipped += 1
            progress[public_id] = {"skipped": "already large", "width": have_w}
            continue

        bigger = None
        for size in (args.width, 0):          # 0 = Blogger's untouched original
            data, problem = fetch(blogger_url_at(item["source"], size))
            if problem:
                continue
            new_w, new_h = image_size(data)
            if new_w and new_w > have_w:
                bigger = (data, new_w, new_h, size)
                break

        if not bigger:
            print("  %s %s  %dx%d — Blogger has nothing bigger" %
                  (position, label, have_w, have_h))
            needs_human.append((label, "%dx%d" % (have_w, have_h)))
            failed += 1
            continue

        data, new_w, new_h, got_at = bigger
        change = "%dx%d -> %dx%d" % (have_w, have_h, new_w, new_h)

        if not args.apply:
            print("  %s %s  %s  (%d KB, =s%d)" %
                  (position, label, change, len(data) // 1024, got_at), flush=True)
            done += 1
            uploaded_bytes += len(data)
            continue

        try:
            uploader.upload(
                data,
                public_id=public_id,
                overwrite=True,        # the whole point: replace, don't add
                invalidate=True,       # purge the CDN copies of the old thumbnail
                resource_type="image",
                # Cap on the way in, as the original migration did, so a 4845px
                # photo doesn't land on an account that has no room for it.
                transformation=[{"width": args.width, "crop": "limit",
                                 "quality": "auto:good"}],
            )
        except Exception as exc:                      # noqa: BLE001
            print("  %s %s  upload failed: %s" % (position, label, exc), flush=True)
            failed += 1
            continue

        print("  %s %s  %s  (%d KB)" % (position, label, change, len(data) // 1024), flush=True)
        progress[public_id] = {"was": "%dx%d" % (have_w, have_h),
                               "now": "%dx%d" % (new_w, new_h),
                               "bytes": len(data), "at": int(time.time())}
        save_progress(progress)
        done += 1
        uploaded_bytes += len(data)
        time.sleep(args.delay)

    if args.apply:
        save_progress(progress)

    print("\n%s %d image(s), about %.0f MB." %
          ("replaced" if args.apply else "would replace", done, uploaded_bytes / 1048576.0))
    if skipped:
        print("%d were already big enough." % skipped)
    if needs_human:
        print("\n%d cannot be fixed from Blogger and need a real re-upload in "
              "the editor:" % len(needs_human))
        for label, size in needs_human:
            print("    %s  (stored at %s)" % (label, size))
    if failed and not needs_human:
        print("%d failed — re-run to try them again." % failed)
    if args.apply and done:
        print("\nCloudinary regenerates the resized copies after an overwrite, so "
              "give it a few minutes, then hard-refresh a page to see the change.")
    elif not args.apply:
        print("\nNothing was uploaded. Re-run with --apply to do it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

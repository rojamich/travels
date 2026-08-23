#!/usr/bin/env python3
"""
shrink_cloudinary_assets.py — re-store Cloudinary photos at a sane size.

WHY THIS EXISTS
    Cloudinary is a CDN for this site, not an archive: the master copies of
    every photo live in Google Drive. Yet the stored assets average 1.6MB,
    because for months uploads arrived at full phone resolution -- 4000px+,
    4-12MB -- while the site never delivers wider than 1200px.

    Capping new uploads (the travel_blog_upload preset) stops the bleeding.
    This script deals with the ~8,000 photos already stored, which is where
    almost all of the 12GB actually sits.

WHAT IT DOES
    For each asset larger than the target, asks Cloudinary to deliver a
    resized copy of it and re-uploads that copy over the same public_id.
    The public_id never changes, so no URL in any post changes.

COST -- READ THIS BEFORE A FULL RUN
    Roughly one transformation per photo: ~6,800 transformations, about 6.8
    credits of a 25-credit monthly allowance. Each resized copy is also
    downloaded through the CDN before being re-uploaded, which bills as
    delivery bandwidth -- around 2.5GB, so another ~2.5 credits. Call it 9-10
    credits for the full job. That is a real dent in one month's quota, so:

      - Run --limit 20 first and CHECK THE SITE (see VERIFY below).
      - Run the bulk after the monthly window has room, in batches.
      - Do not start a full run while already over the limit; Cloudinary
        throttles transformations for accounts in overage.

    The storage saving is permanent and roughly 9GB, so it pays back within
    the first month and every month after.

VERIFY BEFORE THE BULK RUN
    Overwriting an asset gives it a NEW version number, while the URLs
    already written into _posts/ carry the OLD one, e.g. /v1785669755/.
    Cloudinary treats the version as a cache hint rather than an address,
    so those URLs are expected to keep working -- but "expected" is not
    good enough across 8,000 photos on every post of the site.

    So: run --limit 20, then open the posts those photos appear in (the
    script prints them) and confirm the images still load. If any 404, STOP
    -- the job then also has to rewrite URLs in the markdown, which is a
    different and much larger piece of work.

SAFETY
    - --dry-run shows the plan and writes nothing.
    - Resumable: every finished public_id is recorded in .audit/, so a
      re-run skips completed work and batches can be spread over weeks.
    - Skips anything already at or below the target.
    - Format is preserved; only pixel dimensions and quality change.
    - THIS OVERWRITES THE STORED ORIGINAL. It is only safe because the
      masters are in Google Drive. Confirm that is still true before
      running -- the script asks.

CREDENTIALS
    Needs your Cloudinary API secret. Do NOT paste it into a chat or commit
    it. Set it as an environment variable for the run:

        Windows (PowerShell):
            $env:CLOUDINARY_URL = "cloudinary://<api_key>:<api_secret>@dgw35sldo"
        macOS / Linux:
            export CLOUDINARY_URL="cloudinary://<api_key>:<api_secret>@dgw35sldo"

USAGE
        python scripts/shrink_cloudinary_assets.py --dry-run
        python scripts/shrink_cloudinary_assets.py --limit 20    # then VERIFY
        python scripts/shrink_cloudinary_assets.py --limit 2000  # a batch
"""

import argparse
import datetime as dt
import io
import json
import os
import sys
import time
import urllib.request

AUDIT_DIR = ".audit"
ASSET_CACHE = os.path.join(AUDIT_DIR, "cloudinary_assets.json")
PROGRESS_FILE = os.path.join(AUDIT_DIR, "shrink_progress.json")
CLOUD_NAME = "dgw35sldo"

# Delivery caps at 1200px wide. Storing at 1600 leaves headroom for a future
# wider layout or a 2x display without re-uploading everything from Drive,
# and costs little: 1600px is under half the pixels of 2400.
DEFAULT_TARGET_WIDTH = 1600
DEFAULT_QUALITY = "auto:good"


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding="utf-8") as handle:
            return json.load(handle)
    return {"done": {}, "failed": {}}


def save_progress(progress):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as handle:
        json.dump(progress, handle, indent=1)


def load_assets(refresh):
    """Reuse the audit script's cached listing, or fetch a fresh one."""
    if refresh and not os.environ.get("CLOUDINARY_URL"):
        print("--refresh needs CLOUDINARY_URL; falling back to the cached list.")
        refresh = False
    if os.path.exists(ASSET_CACHE) and not refresh:
        with open(ASSET_CACHE, encoding="utf-8") as handle:
            assets = json.load(handle)
        age = dt.datetime.now() - dt.datetime.fromtimestamp(os.path.getmtime(ASSET_CACHE))
        print(f"Using cached asset list from {int(age.total_seconds() // 60)} min ago "
              f"(--refresh to re-fetch)")
        return assets

    import cloudinary.api
    print("Listing assets from Cloudinary...")
    assets, cursor = [], None
    while True:
        page = cloudinary.api.resources(
            resource_type="image", type="upload", max_results=500, next_cursor=cursor,
        )
        assets.extend(page.get("resources", []))
        cursor = page.get("next_cursor")
        print(f"  ...{len(assets):,} listed", end="\r", flush=True)
        if not cursor:
            break
    print(" " * 40, end="\r")
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(ASSET_CACHE, "w", encoding="utf-8") as handle:
        json.dump(assets, handle)
    return assets


def source_url(asset, width, quality):
    """The asset's own delivery URL, resized -- this is what we re-upload.

    c_limit only shrinks: a photo already narrower than the target passes
    through untouched rather than being blown up. No f_ parameter, so the
    format comes back exactly as stored and a .heic stays a .heic.
    """
    fmt = asset.get("format", "jpg")
    return (
        f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/"
        f"c_limit,w_{width},q_{quality}/v{asset['version']}/{asset['public_id']}.{fmt}"
    )


def fetch_resized(url, attempts=3):
    """Download the resized copy ourselves, and hand Cloudinary the bytes.

    The upload API can fetch a remote URL directly, which would save a round
    trip. Pointed at res.cloudinary.com it answers 420 for every asset --
    it will not have its uploader pull from its own delivery domain. The very
    same URLs return 200 to an ordinary client, so be an ordinary client.

    Retries with backoff: one flaky download should not cost the batch.
    """
    request = urllib.request.Request(url, headers={"User-Agent": "travel-blog-shrink"})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception:  # noqa: BLE001 -- retry anything, re-raise at the end
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


def needs_shrinking(asset, width, min_bytes):
    if asset.get("width", 0) > width:
        return True
    # A photo already narrow enough can still be a needlessly heavy file --
    # an uncompressed 1200px export runs several MB. Re-encoding at q_auto
    # fixes that without touching its dimensions.
    return asset.get("bytes", 0) > min_bytes


def mb(byte_count):
    return byte_count / 1048576


def main():
    parser = argparse.ArgumentParser(
        description="Re-store Cloudinary photos at a smaller size, in place."
    )
    parser.add_argument("--target-width", type=int, default=DEFAULT_TARGET_WIDTH,
                        help=f"max stored width (default {DEFAULT_TARGET_WIDTH})")
    parser.add_argument("--quality", default=DEFAULT_QUALITY,
                        help=f"Cloudinary quality (default {DEFAULT_QUALITY})")
    parser.add_argument("--min-bytes", type=int, default=400 * 1024,
                        help="also re-encode anything above this size even if "
                             "its width is fine (default 400KB)")
    parser.add_argument("--limit", type=int,
                        help="process at most this many (use 20 for the first run)")
    parser.add_argument("--dry-run", action="store_true",
                        help="show the plan, change nothing")
    parser.add_argument("--refresh", action="store_true",
                        help="re-fetch the asset list instead of using the cache")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="seconds between uploads (default 0.1)")
    args = parser.parse_args()

    if not args.dry_run and not os.environ.get("CLOUDINARY_URL"):
        sys.exit("No CLOUDINARY_URL set -- see the CREDENTIALS section above.")

    assets = load_assets(args.refresh)
    progress = load_progress()

    # A cached list written before an orphan purge still names deleted assets,
    # and their source URLs now 404 -- every one of those becomes a failed
    # upload. Say so rather than letting the run discover it one 404 at a time.
    age_hours = 0.0
    if os.path.exists(ASSET_CACHE):
        age_hours = (time.time() - os.path.getmtime(ASSET_CACHE)) / 3600
    if not args.refresh and age_hours > 1:
        print(f"\n  NOTE: asset list is {age_hours:.0f}h old. If you have deleted or "
              f"uploaded\n  anything since, re-run with --refresh.")

    todo = [
        a for a in assets
        if a["public_id"] not in progress["done"]
        and needs_shrinking(a, args.target_width, args.min_bytes)
    ]
    todo.sort(key=lambda a: -a.get("bytes", 0))  # biggest wins first

    skipped = len(assets) - len(todo) - len(progress["done"])
    current_bytes = sum(a.get("bytes", 0) for a in todo)

    print(f"\n  stored assets      : {len(assets):,}")
    print(f"  already done       : {len(progress['done']):,}")
    print(f"  already small      : {skipped:,}")
    print(f"  to shrink          : {len(todo):,}   ({mb(current_bytes) / 1024:.2f} GB)")
    if args.limit:
        todo = todo[:args.limit]
        print(f"  this run (--limit) : {len(todo):,}")

    if not todo:
        print("\nNothing to do.")
        return

    if args.dry_run:
        print("\n--dry-run: 10 largest that would be processed:\n")
        for a in todo[:10]:
            print(f"  {mb(a.get('bytes', 0)):7.2f} MB  {a.get('width')}x{a.get('height')}"
                  f"  {a['public_id']}")
        print(f"\nEach would be re-stored via:\n  {source_url(todo[0], args.target_width, args.quality)}")
        print("\nNothing changed.")
        return

    print(f"\nThis OVERWRITES the stored original of {len(todo):,} photos on Cloudinary.")
    print("Cloudinary keeps no previous copy. The masters in Google Drive are")
    print("the only way back.")
    print(f"Cost: roughly {len(todo):,} transformations.")
    if input('Type "shrink" to proceed: ').strip() != "shrink":
        sys.exit("Aborted -- nothing changed.")

    import cloudinary.uploader

    before_total = after_total = 0
    failures = 0
    for i, asset in enumerate(todo, 1):
        public_id = asset["public_id"]
        before = asset.get("bytes", 0)
        try:
            data = fetch_resized(source_url(asset, args.target_width, args.quality))
            # Never make a file bigger. Re-encoding can inflate an already
            # well-compressed photo, and overwriting it with a worse copy
            # would spend a transformation to lose ground and quality.
            if before and len(data) >= before:
                progress["done"][public_id] = {"before": before, "after": before,
                                               "skipped": "would not shrink"}
                continue
            result = cloudinary.uploader.upload(
                io.BytesIO(data),
                public_id=public_id,
                overwrite=True,
                invalidate=True,      # drop the old copy from the CDN edge
                resource_type="image",
            )
        except Exception as exc:  # noqa: BLE001 -- keep going, record the casualty
            failures += 1
            progress["failed"][public_id] = str(exc)[:200]
            print(f"  [{i}/{len(todo)}] FAILED {public_id}: {str(exc)[:80]}")
            if failures >= 10 and failures == i:
                save_progress(progress)
                sys.exit("\nFirst 10 uploads all failed -- stopping. Check the error "
                         "above; nothing else has been touched.")
            continue

        after = result.get("bytes", 0)
        before_total += before
        after_total += after
        progress["done"][public_id] = {"before": before, "after": after}
        if i % 25 == 0 or i == len(todo):
            save_progress(progress)
            saved = mb(before_total - after_total) / 1024
            print(f"  [{i}/{len(todo)}] {public_id[:40]:40s} "
                  f"{mb(before):6.2f} -> {mb(after):5.2f} MB   saved {saved:.2f} GB")
        time.sleep(args.delay)

    save_progress(progress)
    print(f"\nDone. {len(todo) - failures:,} shrunk, {failures} failed.")
    print(f"  {mb(before_total):,.0f} MB -> {mb(after_total):,.0f} MB "
          f"({mb(before_total - after_total) / 1024:.2f} GB saved this run)")

    print("\nNOW VERIFY -- open the posts using these photos and confirm they "
          "still load:")
    for asset in todo[:5]:
        print(f"  https://res.cloudinary.com/{CLOUD_NAME}/image/upload/"
              f"c_limit,f_auto,q_auto,w_1200/v{asset['version']}/{asset['public_id']}"
              f".{asset.get('format', 'jpg')}")
    print("\nThose are the OLD version numbers, as written in _posts/. If they "
          "load, the\nremaining batches are safe. If any 404, stop and rewrite "
          "the URLs first.")


if __name__ == "__main__":
    main()

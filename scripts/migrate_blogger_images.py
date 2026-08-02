#!/usr/bin/env python3
"""
migrate_blogger_images.py — move Blogger-hosted photos onto Cloudinary.

WHY THIS EXISTS
    ~6,000 distinct images across ~220 posts are still hotlinked from
    blogger.googleusercontent.com, carried over by the original import.
    They work today, but they live on an account/service we don't control.
    If that Blogger blog is deleted or Google rotates those URLs, every one
    of those posts loses its photos with no way back.

WHAT IT DOES
    1. Scans _posts/ and _trips/ for blogger.googleusercontent.com URLs.
    2. Downloads each one.
    3. Uploads it to Cloudinary under the blogger-import/ folder.
    4. Rewrites the markdown to point at the new Cloudinary URL.

SAFETY
    - Resumable. Every completed image is recorded in the mapping file, so
      re-running skips finished work. Safe to stop and restart.
    - Files are only rewritten after ALL their images upload successfully.
      A partial failure leaves that post untouched rather than half-migrated.
    - --dry-run shows the full plan and writes nothing.
    - Originals stay on Blogger; nothing is deleted anywhere.

CREDENTIALS
    Needs your Cloudinary API secret. Do NOT paste it into a chat or commit
    it. Set it as an environment variable for the run:

        Windows (PowerShell):
            $env:CLOUDINARY_URL = "cloudinary://<api_key>:<api_secret>@dgw35sldo"
        macOS / Linux:
            export CLOUDINARY_URL="cloudinary://<api_key>:<api_secret>@dgw35sldo"

    Find it in the Cloudinary dashboard under Settings -> API Keys.

USAGE
        pip install cloudinary requests
        python scripts/migrate_blogger_images.py --dry-run
        python scripts/migrate_blogger_images.py --limit 25      # try a small batch first
        python scripts/migrate_blogger_images.py                 # full run

    Recommended: run --dry-run, then --limit 25 and check those posts on the
    site, then the full run. Expect the full run to take a while — it is
    thousands of download+upload round trips.
"""

import argparse
import glob
import hashlib
import io
import json
import os
import re
import sys
import time

MAPPING_FILE = ".audit/blogger_to_cloudinary.json"
CLOUD_FOLDER = "blogger-import"
BLOGGER_RE = re.compile(r"https://blogger\.googleusercontent\.com/[^\s\"'<>)\]]+")

# Blogger URLs often carry a size directive like /w161-h189/ or /s320/ which
# serves a thumbnail. Strip it so we archive the largest version available —
# we only get one shot at pulling these down.
SIZE_DIRECTIVE_RE = re.compile(r"/(?:[swh]\d+(?:-[swh]\d+)*|w\d+-h\d+-[a-z-]+)/")


def upsize(url):
    return SIZE_DIRECTIVE_RE.sub("/s0/", url)


def stable_id(url):
    """Deterministic Cloudinary public_id for a source URL.

    Must NOT use Python's built-in hash(): it is salted per process, so the
    same URL would produce a different id on every run and a resumed or
    repeated migration would silently upload duplicates.
    """
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]


def fetch_with_retry(session_holder, url, retries, base_delay, verbose=True):
    """Download a Blogger image, retrying through transient disconnects.

    Blogger throttles bursts of sequential requests by closing the connection
    outright — surfaced as RemoteDisconnected / ConnectionError rather than an
    HTTP status. It is transient: backing off and retrying almost always
    succeeds.

    A dropped connection can also poison the pooled keep-alive socket, so we
    rebuild the session before each retry rather than reusing a broken one.
    session_holder is a one-item list so the replacement is visible to the
    caller.
    """
    import requests

    last = None
    for attempt in range(retries + 1):
        try:
            resp = session_holder[0].get(url, timeout=60)
            resp.raise_for_status()
            return resp.content
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            last = exc
            if attempt == retries:
                break
            wait = base_delay * (2 ** attempt)
            if verbose:
                print(f"      retry {attempt + 1}/{retries} in {wait:.0f}s "
                      f"({type(exc).__name__})")
            time.sleep(wait)
            session_holder[0] = new_session()
    raise last


def new_session():
    import requests
    sess = requests.Session()
    sess.headers["User-Agent"] = "Mozilla/5.0 (travel-blog image migration)"
    return sess


def load_mapping():
    if os.path.exists(MAPPING_FILE):
        with io.open(MAPPING_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def save_mapping(mapping):
    os.makedirs(os.path.dirname(MAPPING_FILE), exist_ok=True)
    with io.open(MAPPING_FILE, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=1, ensure_ascii=False)


def collect():
    """Return {filepath: [urls]} for every content file with Blogger images."""
    found = {}
    for path in sorted(glob.glob("_posts/*.md") + glob.glob("_trips/*.md")):
        text = io.open(path, encoding="utf-8", errors="replace").read()
        urls = BLOGGER_RE.findall(text)
        if urls:
            # dedupe but keep order
            seen, ordered = set(), []
            for u in urls:
                if u not in seen:
                    seen.add(u)
                    ordered.append(u)
            found[path] = ordered
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="plan only, write nothing")
    ap.add_argument("--limit", type=int, default=0, help="stop after N files (0 = all)")
    ap.add_argument("--delay", type=float, default=0.4,
                    help="seconds between uploads (raise if Blogger keeps dropping)")
    ap.add_argument("--retries", type=int, default=4,
                    help="retry attempts per image on a dropped connection")
    args = ap.parse_args()

    found = collect()
    total_files = len(found)
    total_urls = sum(len(v) for v in found.values())
    distinct = len({u for v in found.values() for u in v})

    print(f"files with Blogger images : {total_files}")
    print(f"image references          : {total_urls}")
    print(f"distinct images           : {distinct}")

    mapping = load_mapping()
    if mapping:
        print(f"already migrated          : {len(mapping)} (will be skipped)")

    if args.dry_run:
        print("\n--dry-run: nothing will be downloaded, uploaded or rewritten.\n")
        for path, urls in list(found.items())[: args.limit or 12]:
            print(f"  {os.path.basename(path)}  ({len(urls)} images)")
        if total_files > (args.limit or 12):
            print(f"  ... and {total_files - (args.limit or 12)} more files")
        return 0

    try:
        import requests
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        print("\nMissing dependencies. Run:\n    pip install cloudinary requests")
        return 1

    if not os.environ.get("CLOUDINARY_URL"):
        print("\nCLOUDINARY_URL is not set — see the header of this file for how to set it.")
        return 1
    cloudinary.config(secure=True)

    session_holder = [new_session()]

    processed = 0
    for path, urls in found.items():
        if args.limit and processed >= args.limit:
            break

        rewrites = {}
        failed = False

        for url in urls:
            if url in mapping:
                rewrites[url] = mapping[url]
                continue

            try:
                content = fetch_with_retry(session_holder, upsize(url),
                                           args.retries, base_delay=2.0)

                result = cloudinary.uploader.upload(
                    content,
                    folder=CLOUD_FOLDER,
                    # Same URL twice always resolves to the same asset, so a
                    # re-run can't create duplicates even if the mapping file
                    # is lost.
                    public_id=stable_id(url),
                    overwrite=False,
                    resource_type="image",
                    # Incoming transformation: resize BEFORE storing, so 6,000
                    # images don't consume the storage quota at full size. We
                    # only ever deliver at 1200px wide, so a 2400px cap is
                    # invisible on the site but roughly halves what's kept.
                    transformation=[{"width": 2400, "crop": "limit",
                                     "quality": "auto:good"}],
                )
                new_url = result["secure_url"]
                mapping[url] = new_url
                rewrites[url] = new_url
                print(f"    ok  {os.path.basename(path)}  {len(rewrites)}/{len(urls)}")
                time.sleep(args.delay)

            except Exception as exc:  # noqa: BLE001 - report and move on
                print(f"    FAIL {os.path.basename(path)}: {exc}")
                failed = True
                break

        # Only rewrite once every image for this file is safely on Cloudinary.
        if failed:
            print(f"  skipped rewrite of {os.path.basename(path)} (an image failed)")
            save_mapping(mapping)
            continue

        text = io.open(path, encoding="utf-8", newline="").read()
        for old, new in rewrites.items():
            text = text.replace(old, new)
        io.open(path, "w", encoding="utf-8", newline="").write(text)
        print(f"  rewrote {os.path.basename(path)}")

        save_mapping(mapping)
        processed += 1

    save_mapping(mapping)
    print(f"\ndone. files rewritten: {processed}   images migrated: {len(mapping)}")
    print("Review with `git diff`, then commit and push.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

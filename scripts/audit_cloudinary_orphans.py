#!/usr/bin/env python3
"""
audit_cloudinary_orphans.py — find Cloudinary assets no page on the site uses.

WHY THIS EXISTS
    Storage is the biggest line on the Cloudinary bill, and unlike bandwidth
    and transformations it never rolls off — every photo ever uploaded keeps
    costing until it is deleted. As of the August 2026 audit Cloudinary held
    ~12,160 assets while only ~7,800 were referenced anywhere on the site.
    The rest are deleted posts, duplicate uploads and abandoned import runs:
    storage rent for files no visitor can reach.

WHAT IT DOES
    1. Scans the whole repo for Cloudinary URLs and works out which asset
       each one points at (ignoring the transformation and version parts).
    2. Asks Cloudinary's Admin API for every asset it actually stores.
    3. Prints the difference and writes two CSVs into .audit/:
         orphans.csv  — stored but never referenced (candidates to delete)
         missing.csv  — referenced but NOT stored (broken images on the site)

SAFETY
    - Reports only. Deleting requires the explicit --delete flag AND typing
      a confirmation phrase. Nothing is removed just by running the audit.
    - Assets newer than --min-age-days (default 7) are never treated as
      orphans, so a photo uploaded today but not yet written into a post
      can't be swept away.
    - --delete refuses to run if the "missing" list looks implausibly large,
      which is the signature of URL parsing having gone wrong. A broken
      parser would classify live photos as orphans, so it must fail loud.
    - Deletion is permanent. Cloudinary has no trash. Read orphans.csv
      first — that is the whole point of writing it out.

CREDENTIALS
    Needs your Cloudinary API secret. Do NOT paste it into a chat or commit
    it. Set it as an environment variable for the run:

        Windows (PowerShell):
            $env:CLOUDINARY_URL = "cloudinary://<api_key>:<api_secret>@dgw35sldo"
        macOS / Linux:
            export CLOUDINARY_URL="cloudinary://<api_key>:<api_secret>@dgw35sldo"

    Find it in the Cloudinary dashboard under Settings -> API Keys.

USAGE
        pip install cloudinary
        python scripts/audit_cloudinary_orphans.py              # audit, writes CSVs
        python scripts/audit_cloudinary_orphans.py --delete     # after reviewing!
"""

import argparse
import csv
import datetime as dt
import os
import re
import sys
import urllib.parse

AUDIT_DIR = ".audit"
ORPHAN_CSV = os.path.join(AUDIT_DIR, "orphans.csv")
MISSING_CSV = os.path.join(AUDIT_DIR, "missing.csv")

# Directories that never contain hand-written references: build output, VCS
# internals, dependencies. Everything else in the repo is fair game, because
# a URL hiding in an unscanned file is how a live photo gets called an orphan.
SKIP_DIRS = {
    "_site", ".git", ".jekyll-cache", ".sass-cache", "vendor",
    "node_modules", "__pycache__", ".bundle",
    # Local audit/migration working files, not site content. The Blogger
    # import mapping in here lists every asset that migration ever uploaded,
    # so counting it as a reference would permanently protect imports whose
    # posts have since been edited or deleted - exactly what we're hunting.
    ".audit",
}
SKIP_EXTS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".ico", ".pdf",
    ".zip", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mov",
}

CLOUD_NAME = "dgw35sldo"
URL_RE = re.compile(
    r"res\.cloudinary\.com/" + CLOUD_NAME +
    # Stop at anything that can't be part of a URL in markdown, HTML, YAML or
    # JSON - backticks and brackets included, or prose in the docs gets
    # swallowed into the public_id and shows up as a phantom broken reference.
    r"/(?:image|video|raw)/upload/([^\"'\)\s<>\\`\[\]{}|]+)"
)
VERSION_RE = re.compile(r"^v\d+$")
# A transformation segment is one or more "xx_value" params joined by commas,
# e.g. c_limit,f_auto,q_auto,w_1200 - or a named transform, t_something.
TRANSFORM_RE = re.compile(r"^[a-z]{1,3}_[^/,]+(?:,[a-z]{1,3}_[^/,]+)*$")
MEDIA_EXT_RE = re.compile(r"\.(jpe?g|png|gif|webp|avif|svg|bmp|mp4|mov|pdf)$", re.I)


def public_id_from_path(path):
    """Turn the bit after /upload/ into a bare public_id.

    'c_limit,f_auto/v1785669755/blogger-import/abc.jpg' -> 'blogger-import/abc'

    Transformation and version segments are stripped; so is the file
    extension, because Cloudinary's public_id does not include it.

    The version segment is the reliable anchor: everything after it is the
    public_id, full stop. Without that anchor a filename like 'img_1234.jpg'
    is indistinguishable from a transformation ('img' reads as a 3-letter
    param name), and stripping it would silently mislabel a live photo as
    an orphan - so only segments BEFORE the version are ever discarded.
    """
    segments = path.split("/")
    for i, segment in enumerate(segments):
        if VERSION_RE.match(segment):
            segments = segments[i + 1:]
            break
    else:
        # No version in the URL. Strip leading transformation segments, but
        # never the last one - that is the filename, whatever it looks like.
        while len(segments) > 1 and TRANSFORM_RE.match(segments[0]):
            segments.pop(0)
    if not segments:
        return None
    public_id = "/".join(segments)
    return MEDIA_EXT_RE.sub("", public_id) or None


def scan_repo(root="."):
    """Every public_id referenced anywhere in the repo, and where it appears."""
    found = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in SKIP_EXTS:
                continue
            full = os.path.join(dirpath, name)
            try:
                text = open(full, encoding="utf-8", errors="replace").read()
            except (OSError, ValueError):
                continue
            if "cloudinary" not in text:
                continue
            # Gallery blocks store their JSON percent-encoded, so the raw text
            # holds no readable URL at all. Scan the decoded copy too and take
            # the union - missing these would flag ~2,000 live photos as junk.
            for blob in (text, urllib.parse.unquote(text)):
                for match in URL_RE.findall(blob):
                    public_id = public_id_from_path(match)
                    if public_id:
                        found.setdefault(public_id, set()).add(
                            os.path.relpath(full, root).replace("\\", "/")
                        )
    return found


def fetch_stored(resource_types=("image", "video")):
    """Every asset Cloudinary is storing, via the Admin API."""
    import cloudinary
    import cloudinary.api

    if not (os.environ.get("CLOUDINARY_URL") or cloudinary.config().api_secret):
        sys.exit(
            "No Cloudinary credentials found.\n"
            "Set CLOUDINARY_URL first - see the CREDENTIALS section at the top "
            "of this file."
        )

    assets = []
    for resource_type in resource_types:
        cursor = None
        while True:
            try:
                page = cloudinary.api.resources(
                    resource_type=resource_type,
                    type="upload",
                    max_results=500,
                    next_cursor=cursor,
                )
            except Exception as exc:  # noqa: BLE001 - surface the API's own message
                sys.exit(f"Cloudinary API error listing {resource_type}s: {exc}")
            assets.extend(page.get("resources", []))
            cursor = page.get("next_cursor")
            print(f"  ...{len(assets):,} assets listed", end="\r", flush=True)
            if not cursor:
                break
    print(" " * 40, end="\r")
    return assets


def human_gb(byte_count):
    return byte_count / (1024 ** 3)


def write_csv(path, header, rows):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Find Cloudinary assets no page on the site uses."
    )
    parser.add_argument("--min-age-days", type=int, default=7,
                        help="never call an asset newer than this an orphan "
                             "(default 7, protects uploads not yet in a post)")
    parser.add_argument("--delete", action="store_true",
                        help="permanently delete the orphans (asks first)")
    args = parser.parse_args()

    print("Scanning repo for Cloudinary references...")
    referenced = scan_repo(".")
    print(f"  {len(referenced):,} distinct assets referenced on the site\n")

    print("Listing assets stored in Cloudinary...")
    stored = fetch_stored()
    print(f"  {len(stored):,} assets stored\n")

    stored_ids = {a["public_id"] for a in stored}
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.min_age_days)

    orphans, too_new = [], 0
    for asset in stored:
        if asset["public_id"] in referenced:
            continue
        created = asset.get("created_at", "")
        try:
            created_dt = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
        except ValueError:
            created_dt = None
        if created_dt and created_dt > cutoff:
            too_new += 1
            continue
        orphans.append(asset)

    missing = sorted(pid for pid in referenced if pid not in stored_ids)

    # A parser that mangles public_ids produces two symptoms at once: a huge
    # "missing" list and an inflated "orphan" list. Missing is the honest
    # canary, because a real site rarely links thousands of dead images.
    missing_ratio = len(missing) / max(len(referenced), 1)

    orphan_bytes = sum(a.get("bytes", 0) for a in orphans)
    total_bytes = sum(a.get("bytes", 0) for a in stored)

    write_csv(
        ORPHAN_CSV,
        ["public_id", "format", "megabytes", "created_at", "url"],
        [[a["public_id"], a.get("format", ""), round(a.get("bytes", 0) / 1048576, 3),
          a.get("created_at", ""), a.get("secure_url", "")] for a in
         sorted(orphans, key=lambda a: -a.get("bytes", 0))],
    )
    write_csv(
        MISSING_CSV,
        ["public_id", "referenced_in"],
        [[pid, "; ".join(sorted(referenced[pid]))] for pid in missing],
    )

    print("=" * 62)
    print(f"  stored in Cloudinary : {len(stored):>7,}   {human_gb(total_bytes):>6.2f} GB")
    print(f"  used by the site     : {len(stored) - len(orphans) - too_new:>7,}")
    print(f"  too new to judge     : {too_new:>7,}   (< {args.min_age_days} days old)")
    print(f"  ORPHANED             : {len(orphans):>7,}   {human_gb(orphan_bytes):>6.2f} GB reclaimable")
    print("=" * 62)
    print(f"\n  broken references    : {len(missing):,} "
          f"({missing_ratio:.1%} of referenced assets)")
    print(f"\nWrote {ORPHAN_CSV} and {MISSING_CSV}")

    if not args.delete:
        print("\nReport only - nothing deleted. Review orphans.csv, then re-run")
        print("with --delete if it looks right.")
        return

    if missing_ratio > 0.05:
        sys.exit(
            f"\nREFUSING TO DELETE: {missing_ratio:.1%} of referenced assets were not "
            f"found in Cloudinary.\nThat usually means URL parsing broke, not that the "
            f"site is full of dead images -\nand a broken parser mislabels live photos "
            f"as orphans. Check {MISSING_CSV} first."
        )
    if not orphans:
        print("\nNothing to delete.")
        return

    print(f"\nAbout to PERMANENTLY delete {len(orphans):,} assets "
          f"({human_gb(orphan_bytes):.2f} GB).")
    print("Cloudinary has no trash. This cannot be undone.")
    if input('Type "delete orphans" to proceed: ').strip() != "delete orphans":
        sys.exit("Aborted - nothing deleted.")

    import cloudinary.api
    ids = [a["public_id"] for a in orphans]
    deleted = 0
    for i in range(0, len(ids), 100):  # Admin API caps at 100 per call
        batch = ids[i:i + 100]
        cloudinary.api.delete_resources(batch, invalidate=True)
        deleted += len(batch)
        print(f"  deleted {deleted:,}/{len(ids):,}", end="\r", flush=True)
    print(f"\nDeleted {deleted:,} assets, freeing ~{human_gb(orphan_bytes):.2f} GB.")


if __name__ == "__main__":
    main()

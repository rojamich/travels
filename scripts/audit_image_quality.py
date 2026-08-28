#!/usr/bin/env python3
"""
audit_image_quality.py — find photos too small for where they are shown
=============================================================================
WHY
    reimport_lowres_blogger_images.py fixed the 233 images the Blogger import
    brought over as =s320 thumbnails. It could only fix the ones Blogger still
    had at a larger size, and it knew nothing about photos uploaded straight
    into the editor. This finds whatever is still too small, so the short list
    that genuinely needs re-uploading by hand is a list rather than a surprise
    on some future page.

HOW IT JUDGES
    "Low quality" only means anything relative to how big the image is drawn:

      banner / cover     stretched across the full width of the window, so it
                         wants 1200px at the very least and looks better above
                         1600. Under 800 is visibly bad.
      teaser             the card image on a trip or archive page, ~600px.
      body               inside the post column, ~700px on a wide screen, and
                         clickable to full size in the lightbox.

    A 320px photo is fine as a teaser and terrible as a banner. The same file
    can therefore appear once, twice or not at all.

WHERE THE SIZES COME FROM
    .audit/cloudinary_assets.json — the listing written by
    shrink_cloudinary_assets.py --refresh, which carries width and height for
    every asset. That means no downloading: 5,800 images are judged from a file
    already on disk. Anything not in it (uploaded since that listing was taken)
    is measured over the network, which is a handful of requests.

    .audit/reimport_progress.json is layered on top, because the images the
    re-import replaced are larger now than the cached listing says.

    If the listing is old and the numbers look wrong, refresh it:
        python scripts/shrink_cloudinary_assets.py --refresh --dry-run

USAGE
    python scripts/audit_image_quality.py                  # the report
    python scripts/audit_image_quality.py --csv            # also write a CSV
    python scripts/audit_image_quality.py --role banner    # just the banners

Exit codes: 0 = ran (whether or not it found anything), 1 = could not run.
"""

import argparse
import csv
import glob
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_DIR = os.path.join(ROOT, ".audit")
ASSETS_FILE = os.path.join(AUDIT_DIR, "cloudinary_assets.json")
PROGRESS_FILE = os.path.join(AUDIT_DIR, "reimport_progress.json")
REPORT_FILE = os.path.join(AUDIT_DIR, "image_quality.csv")
CONTENT_DIRS = ("_posts", "_trips")

# What each role needs, in pixels of stored width: (soft below, bad below).
#
# Width, not area: everything here is drawn to fit a container's width, so a
# 746x1600 portrait fills a 700px column perfectly and a 1600x746 panorama is
# equally fine. Judging by the smaller side would flag every tall phone photo
# on the site.
THRESHOLDS = {
    "banner": (1200, 800),   # full window width
    "cover": (1200, 800),    # trip cards, drawn large on /trips/
    "teaser": (700, 500),    # archive thumbnails
    "body": (700, 450),      # the post column, about 700px on a wide screen
}

CLOUDINARY_URL_RE = re.compile(
    r"https://res\.cloudinary\.com/dgw35sldo/image/upload/"
    r"(?:[^/\s\"')]+/)*?v\d+/([^\s\"')]+?)\.(?:jpg|jpeg|png|gif|webp)", re.I)
FRONT_MATTER_ROLE_RE = re.compile(r"^\s*(overlay_image|teaser|cover)\s*:", re.I)


def image_size(data):
    """(width, height) from the first bytes of a JPEG or PNG."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
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


def measure_online(public_id):
    """Last resort for an asset the cached listing has never seen."""
    for extension in ("jpg", "png", "jpeg"):
        url = ("https://res.cloudinary.com/dgw35sldo/image/upload/%s.%s"
               % (public_id, extension))
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "travel-blog audit", "Accept": "image/*",
                              "Range": "bytes=0-65535"})
            with urllib.request.urlopen(request, timeout=20) as response:
                width, height = image_size(response.read())
                if width:
                    return public_id, width, height
        except Exception:                             # noqa: BLE001 - try the next one
            continue
    return public_id, None, None


def role_of_line(line):
    found = FRONT_MATTER_ROLE_RE.match(line)
    if not found:
        return "body"
    field = found.group(1).lower()
    return "banner" if field == "overlay_image" else field


def collect_references():
    """[(public_id, role, file)] for every Cloudinary image the site points at."""
    references = []
    for directory in CONTENT_DIRS:
        for path in sorted(glob.glob(os.path.join(ROOT, directory, "*.md"))):
            name = os.path.basename(path)
            with open(path, encoding="utf-8") as handle:
                for line in handle:
                    for found in CLOUDINARY_URL_RE.finditer(line):
                        references.append((found.group(1), role_of_line(line), name))
    return references


def known_sizes(public_ids):
    """public_id -> (width, height), from the cached listing plus the re-import."""
    sizes = {}
    if os.path.exists(ASSETS_FILE):
        with open(ASSETS_FILE, encoding="utf-8") as handle:
            for asset in json.load(handle):
                if asset.get("width") and asset.get("public_id"):
                    sizes[asset["public_id"]] = (asset["width"], asset["height"])
    else:
        print("No %s — every size will be fetched over the network, slowly."
              % ASSETS_FILE)

    # The re-import replaced these after the listing was taken, so it wins.
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding="utf-8") as handle:
            for public_id, record in json.load(handle).items():
                if isinstance(record, dict) and "now" in record:
                    width, _, height = record["now"].partition("x")
                    if width.isdigit() and height.isdigit():
                        sizes[public_id] = (int(width), int(height))

    unknown = sorted({p for p in public_ids if p not in sizes})
    if unknown:
        print("measuring %d image(s) the cached listing doesn't cover..." % len(unknown))
        for public_id, width, height in ThreadPoolExecutor(12).map(measure_online, unknown):
            if width:
                sizes[public_id] = (width, height)
    return sizes


def main():
    parser = argparse.ArgumentParser(
        description="Find photos too small for where the site shows them.")
    parser.add_argument("--role", choices=sorted(THRESHOLDS),
                        help="only report this role")
    parser.add_argument("--csv", action="store_true",
                        help="also write .audit/image_quality.csv")
    args = parser.parse_args()

    references = collect_references()
    if not references:
        print("No Cloudinary images found in _posts or _trips.")
        return 1

    sizes = known_sizes({public_id for public_id, _, _ in references})

    findings = []
    unmeasured = set()
    for public_id, role, name in references:
        if args.role and role != args.role:
            continue
        if public_id not in sizes:
            unmeasured.add(public_id)
            continue
        width, height = sizes[public_id]
        soft_below, bad_below = THRESHOLDS[role]
        if width >= soft_below:
            continue
        findings.append({
            "severity": "bad" if width < bad_below else "soft",
            "role": role, "post": name, "width": width, "height": height,
            "public_id": public_id,
        })

    # One line per image per role: the same photo used as banner and in the body
    # is two different problems, but twice in the body is one.
    seen = set()
    unique = []
    for finding in findings:
        key = (finding["public_id"], finding["role"], finding["post"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(finding)
    unique.sort(key=lambda f: (f["severity"] != "bad", f["role"], f["width"]))

    total_images = len({p for p, _, _ in references})
    print("\n%d images referenced by %d posts and trips; %d measured.\n"
          % (total_images, len({n for _, _, n in references}), len(sizes)))

    bad = [f for f in unique if f["severity"] == "bad"]
    soft = [f for f in unique if f["severity"] == "soft"]

    if bad:
        print("TOO SMALL FOR WHERE THEY ARE SHOWN (%d) — worth re-uploading:" % len(bad))
        for f in bad:
            print("  %-7s %5dx%-5d  %s" % (f["role"], f["width"], f["height"], f["post"]))
        print()
    if soft:
        print("SOFT BUT USABLE (%d) — only noticeable on a big screen:" % len(soft))
        for f in soft:
            print("  %-7s %5dx%-5d  %s" % (f["role"], f["width"], f["height"], f["post"]))
        print()
    if not bad and not soft:
        print("Nothing is smaller than the place it is shown. Nothing to do.")
    if unmeasured:
        print("%d image(s) could not be measured at all (deleted from Cloudinary?):"
              % len(unmeasured))
        for public_id in sorted(unmeasured)[:10]:
            print("    %s" % public_id)

    if args.csv:
        os.makedirs(AUDIT_DIR, exist_ok=True)
        with open(REPORT_FILE, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["severity", "role", "post",
                                                        "width", "height", "public_id"])
            writer.writeheader()
            writer.writerows(unique)
        print("Written to %s" % REPORT_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())

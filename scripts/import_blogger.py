"""
=============================================================================
import_blogger.py — convert a Blogger XML export into Jekyll posts
=============================================================================

WHAT THIS DOES
--------------
Takes the giant XML file you get from Blogger's export feature and turns each
post into a Markdown file ready to drop into _posts/.

It will:
  - skip drafts and comments (only published posts become files)
  - convert each post's HTML to Markdown
  - download every image referenced in the post into assets/images/<trip>/
  - rewrite image URLs to point at the local copies
  - generate front matter (title, date, tags, trip category)

HOW TO USE IT
-------------
1. In Blogger, go to:  Settings -> Manage blog -> Back up content
   It downloads a file named something like  blog-MM-DD-YYYY.xml

2. Open a terminal in this project folder. Install the two dependencies:
       pip install -r scripts/requirements.txt

3. Run the script. The required arguments are the input XML path and the
   trip slug to assign every post to:
       python scripts/import_blogger.py blog-04-27-2026.xml --trip iceland-2024

   Optional flags:
       --output _posts          where Markdown goes (default: _posts)
       --images assets/images   where images go (default: assets/images)
       --skip-images            don't download images, just keep original URLs
       --since 2024-01-01       only import posts on/after this date

4. Review the generated files. The script does its best but Blogger HTML can
   be messy — you may want to skim each post and clean up formatting.

NOTES
-----
- One trip per run. If your Blogger blog covers multiple trips, run the
  script multiple times with --since/--until filters, or sort the output
  files into different categories afterward.
- The script never modifies your original XML file.
- It is safe to re-run; existing files with the same name are overwritten.
"""

import argparse
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

try:
    import html2text
except ImportError:
    print("ERROR: html2text is not installed.")
    print("Run:  pip install -r scripts/requirements.txt")
    sys.exit(1)


# Atom XML namespaces used by Blogger's export format.
# Two slightly different shapes exist in the wild:
#   - Old "Back up content" XML: uses atom:category to mark posts vs comments.
#   - New Google Takeout feed.atom: uses <blogger:type>POST</blogger:type>.
# We support both.
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "app": "http://purl.org/atom/app#",
    "blogger": "http://schemas.google.com/blogger/2018",
}


def slugify(text: str) -> str:
    """Turn a post title into a URL-safe slug for the filename."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "untitled"


def is_post(entry) -> bool:
    """The export contains posts, comments, and other entries mixed together.
    We only want published posts.

    Newer Takeout atom feeds tag entries with <blogger:type>POST</blogger:type>.
    Older XML uses <category scheme="...#kind" term="...#post"/>.
    """
    # New Takeout format.
    type_el = entry.find("blogger:type", NS)
    if type_el is not None:
        if (type_el.text or "").strip() != "POST":
            return False
        # Status: only LIVE posts; skip DRAFT/SCHEDULED.
        status_el = entry.find("blogger:status", NS)
        if status_el is not None and (status_el.text or "").strip() != "LIVE":
            return False
        return True

    # Old format fallback.
    for category in entry.findall("atom:category", NS):
        scheme = category.get("scheme", "")
        term = category.get("term", "")
        if scheme.endswith("#kind") and term.endswith("#post"):
            break
    else:
        return False

    # Skip drafts (old format).
    draft = entry.find("app:control/app:draft", NS)
    if draft is not None and draft.text == "yes":
        return False

    return True


def extract_tags(entry) -> list:
    """Pull post tags (everything except the kind=post marker)."""
    tags = []
    for category in entry.findall("atom:category", NS):
        scheme = category.get("scheme", "")
        if scheme.endswith("#kind"):
            continue
        term = category.get("term", "")
        if term:
            tags.append(term)
    return tags


def extract_image_urls(html: str) -> list:
    """Find every <img src="..."> in the HTML."""
    return re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, flags=re.I)


def download_image(url: str, dest_dir: Path) -> Path | None:
    """Download a single image, return the local path. None on failure."""
    try:
        # Build a filename from the URL, stripping query strings.
        parsed = urllib.parse.urlparse(url)
        name = os.path.basename(parsed.path) or "image"
        if "." not in name:
            name += ".jpg"

        dest = dest_dir / name
        # If a file with this name already exists, append a counter.
        counter = 1
        while dest.exists():
            stem, suffix = os.path.splitext(name)
            dest = dest_dir / f"{stem}-{counter}{suffix}"
            counter += 1

        # Pretend to be a browser; some hosts block default urllib UA.
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        return dest
    except Exception as e:
        print(f"   ! failed to download {url}: {e}")
        return None


def process_entry(entry, args, image_dir: Path, order=None):
    """Convert one Atom entry into a Jekyll post file.

    `order` (optional int) is written into the front matter so the trip
    page can sort posts deterministically.
    """
    title_el = entry.find("atom:title", NS)
    content_el = entry.find("atom:content", NS)
    published_el = entry.find("atom:published", NS)

    if title_el is None or content_el is None or published_el is None:
        return None

    title = (title_el.text or "Untitled").strip()
    html = content_el.text or ""
    published = datetime.fromisoformat(published_el.text.replace("Z", "+00:00"))

    if args.since and published.date() < args.since:
        return None
    if args.until and published.date() > args.until:
        return None

    tags = extract_tags(entry)

    # --- handle images ---
    if not args.skip_images:
        image_dir.mkdir(parents=True, exist_ok=True)
        for url in extract_image_urls(html):
            local = download_image(url, image_dir)
            if local is None:
                continue
            # Rewrite this URL in the HTML to the new local path.
            new_path = f"/{local.as_posix()}"
            html = html.replace(url, new_path)

    # --- HTML -> Markdown ---
    converter = html2text.HTML2Text()
    converter.body_width = 0  # don't hard-wrap lines
    converter.unicode_snob = True
    markdown = converter.handle(html).strip()

    # --- build the file ---
    slug = slugify(title)
    date_str = published.strftime("%Y-%m-%d")
    filename = f"{date_str}-{slug}.md"
    out_path = Path(args.output) / filename

    front_matter_lines = [
        "---",
        f'title: "{title.replace(chr(34), chr(39))}"',
        f"date: {date_str}",
        "categories:",
        f"  - {args.trip}",
    ]
    if order is not None:
        front_matter_lines.append(f"order: {order}")
    if tags:
        front_matter_lines.append("tags:")
        for tag in tags:
            front_matter_lines.append(f"  - {tag}")
    front_matter_lines.append("---")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(front_matter_lines) + "\n\n" + markdown + "\n",
        encoding="utf-8",
    )
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("xml_file", help="path to the Blogger XML export")
    parser.add_argument("--trip", required=True,
                        help="trip slug to assign all imported posts to "
                             "(e.g. iceland-2024)")
    parser.add_argument("--output", default="_posts",
                        help="output directory for Markdown files")
    parser.add_argument("--images", default="assets/images",
                        help="directory under which to save downloaded images")
    parser.add_argument("--skip-images", action="store_true",
                        help="leave image URLs pointing at Blogger/Google")
    parser.add_argument("--since", type=lambda s: datetime.fromisoformat(s).date(),
                        help="only import posts on/after this date (YYYY-MM-DD)")
    parser.add_argument("--until", type=lambda s: datetime.fromisoformat(s).date(),
                        help="only import posts on/before this date (YYYY-MM-DD)")
    args = parser.parse_args()

    image_dir = Path(args.images) / args.trip

    print(f"Parsing {args.xml_file} ...")
    tree = ET.parse(args.xml_file)
    root = tree.getroot()

    # First pass: collect all qualifying post entries with their published
    # dates so we can sort chronologically and assign deterministic order.
    candidates = []
    for entry in root.findall("atom:entry", NS):
        if not is_post(entry):
            continue
        pub_el = entry.find("atom:published", NS)
        if pub_el is None or not pub_el.text:
            continue
        pub_dt = datetime.fromisoformat(pub_el.text.replace("Z", "+00:00"))
        if args.since and pub_dt.date() < args.since:
            continue
        if args.until and pub_dt.date() > args.until:
            continue
        candidates.append((pub_dt, entry))

    # Sort oldest -> newest; assign order 1..N in that sequence.
    candidates.sort(key=lambda x: x[0])

    count = 0
    for order, (_pub_dt, entry) in enumerate(candidates, start=1):
        result = process_entry(entry, args, image_dir, order=order)
        if result:
            count += 1
            print(f"   [order={order:3d}] wrote {result}")

    print(f"\nDone. {count} post(s) imported into '{args.output}/'.")
    if not args.skip_images:
        print(f"Images saved under '{image_dir}/'.")
    print("Review the generated files and tweak the order: field if needed.")


if __name__ == "__main__":
    main()

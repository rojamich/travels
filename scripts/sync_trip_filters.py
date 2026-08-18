#!/usr/bin/env python3
"""
sync_trip_filters.py — keep the editor's trip filter list in step with _trips/
=============================================================================
Decap CMS cannot build its "quick filter" buttons dynamically: the list of
view_filters in admin/config.yml has to be spelled out. That means every new
trip needs a matching line there, and it is exactly the kind of chore that
gets forgotten — which is why the filter list in the editor had drifted nine
trips behind the site.

This script writes that list for us. It reads every file in _trips/, skips the
ones marked `published: false` (the Iceland reference template), and rewrites
the block between the two BEGIN/END marker comments inside admin/config.yml.
Nothing outside those markers is touched.

Run it by hand:

    python scripts/sync_trip_filters.py

It also runs automatically in GitHub Actions whenever a file under _trips/
changes (see .github/workflows/sync-trip-filters.yml), so in normal use nobody
has to remember it.

Exit codes: 0 = file is up to date (whether or not it needed changing),
            1 = something was wrong and nothing was written.
"""

import json
import sys
from pathlib import Path

import yaml

# Trip names contain emoji. On Windows the console defaults to cp1252 and
# printing one of those names would otherwise crash the script after it had
# already written the file — confusing, and it fails the GitHub Action too.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
TRIPS_DIR = ROOT / "_trips"
CONFIG = ROOT / "admin" / "config.yml"

BEGIN = "      # --- BEGIN generated trip filters (scripts/sync_trip_filters.py) ---"
END = "      # --- END generated trip filters ---"


def read_front_matter(path):
    """Return a trip file's YAML front matter as a dict (empty if unreadable)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    # Front matter is everything between the first '---' line and the next one.
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return {}
    try:
        return yaml.safe_load(parts[0].lstrip("-\n")) or {}
    except yaml.YAMLError as err:
        print(f"  ! {path.name}: front matter didn't parse ({err}) — skipped")
        return {}


def collect_trips():
    """Every published trip as (label, slug), sorted the way the list reads."""
    trips = []
    for path in sorted(TRIPS_DIR.glob("*.md")):
        fm = read_front_matter(path)
        if fm.get("published") is False:
            continue
        slug = path.stem                      # filename === the category value
        title = str(fm.get("title") or slug).strip()
        trips.append((title, slug))
    # Alphabetical by the label she actually sees, ignoring case so that
    # "the-singaporean-stopover" doesn't sort away from the rest.
    return sorted(trips, key=lambda t: t[0].lower())


def render(trips):
    """The YAML block that goes between the markers."""
    lines = [BEGIN]
    for label, slug in trips:
        # json.dumps gives a correctly escaped double-quoted scalar, which is
        # also valid YAML — this is what keeps a title like
        # "Welcome Home: Tbilisi, Georgia" from breaking the file.
        lines.append(f"      - label: {json.dumps(label, ensure_ascii=False)}")
        lines.append("        field: categories")
        lines.append(f"        pattern: {json.dumps(slug, ensure_ascii=False)}")
    lines.append(END)
    return "\n".join(lines)


def main():
    if not TRIPS_DIR.is_dir():
        print(f"error: no _trips directory at {TRIPS_DIR}")
        return 1
    if not CONFIG.is_file():
        print(f"error: no admin/config.yml at {CONFIG}")
        return 1

    original = CONFIG.read_text(encoding="utf-8")
    if BEGIN not in original or END not in original:
        print(
            "error: the marker comments are missing from admin/config.yml.\n"
            "       The generated block has to sit between these two lines,\n"
            "       indented exactly like this, inside view_filters:\n\n"
            f"{BEGIN}\n{END}\n"
        )
        return 1

    trips = collect_trips()
    if not trips:
        print("error: found no published trips — refusing to empty the filter list")
        return 1

    head, rest = original.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    updated = head + render(trips) + tail

    # Never write a config that Decap couldn't read: a broken admin/config.yml
    # takes the whole editor down, and she'd have no way to fix it herself.
    try:
        yaml.safe_load(updated)
    except yaml.YAMLError as err:
        print(f"error: the rewritten config is not valid YAML, nothing written:\n{err}")
        return 1

    if updated == original:
        print(f"trip filters already up to date ({len(trips)} trips)")
        return 0

    CONFIG.write_text(updated, encoding="utf-8", newline="\n")
    print(f"admin/config.yml updated — {len(trips)} trips:")
    for label, slug in trips:
        print(f"  {label}  ->  {slug}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

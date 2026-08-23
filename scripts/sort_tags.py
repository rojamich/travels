#!/usr/bin/env python3
"""
sort_tags.py — keep _data/tags.yml in alphabetical order
=============================================================================
New tags land at the bottom of the list, because that is where both the CMS
list widget and a hand edit append them. The config file has asked editors to
"keep it alphabetical if you can" for as long as it has existed, which is the
kind of instruction that loses to a busy evening: by August 2026 the tail of
the file read Dinosaurs, Art, Gym, Sunset, Funicular, Rain, Fort, Fun.

That matters because the tag picker on a post is a relation widget, and it
shows the options in file order. An unsorted file means scrolling for a tag
lands you nowhere near where you expect it, and a tag added last week sits
136 rows down instead of under its own letter.

So sort the file instead of asking people to.

WHAT IT TOUCHES
    Only the order of entries in _data/tags.yml, and exact duplicates, which
    are removed. No tag is ever renamed or dropped: the script compares the
    set of names before and after and refuses to write if anything vanished.

Run it by hand:

    python scripts/sort_tags.py

It also runs automatically in GitHub Actions whenever _data/tags.yml changes
on main (see .github/workflows/sort-tags.yml), so in normal use nobody has to
remember it.

Exit codes: 0 = file is in order (whether or not it needed rewriting),
            1 = something was wrong and nothing was written.
"""

import sys
import unicodedata
from pathlib import Path

import yaml

# Tag names can carry accents or emoji. On Windows the console defaults to
# cp1252 and printing one would crash the script after it had already written
# the file -- confusing locally, and it fails the GitHub Action too.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
TAGS_FILE = ROOT / "_data" / "tags.yml"


class IndentedDumper(yaml.SafeDumper):
    """Indent list items under their parent key.

    PyYAML writes sequences flush against the parent by default, which would
    reformat every line of the file and bury the actual change in the diff.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def sort_key(name):
    """Sort the way a person scanning the list expects.

    Case-insensitive, so "iPhone" files under I rather than after Z. Accents
    are folded too: this is a travel blog, so Wānaka, Reykjavík and Kraków
    all appear, and by raw codepoint they sort after every unaccented word
    in their letter -- Wānaka landed past Workout, at the very end of W,
    which is precisely the "it isn't where I expect it" complaint.

    The original name is the tiebreaker, so the order is stable run to run.
    """
    folded = unicodedata.normalize("NFKD", name.lower())
    stripped = "".join(c for c in folded if not unicodedata.combining(c))
    return (stripped, name)


def main():
    if not TAGS_FILE.exists():
        print(f"{TAGS_FILE} not found.")
        return 1

    raw = TAGS_FILE.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        print(f"{TAGS_FILE} is not valid YAML, leaving it alone:\n  {exc}")
        return 1

    if not isinstance(data, dict) or not isinstance(data.get("tags"), list):
        print("Expected a top-level 'tags:' list. Leaving the file alone.")
        return 1

    entries = data["tags"]
    for entry in entries:
        if not isinstance(entry, dict) or "name" not in entry:
            print(f"Entry is not a `- name: ...` mapping: {entry!r}. "
                  "Leaving the file alone.")
            return 1

    # Drop exact repeats, keeping the first. Case-insensitive near-misses are
    # NOT merged -- "Museum" and "Museums" may both be deliberate, and picking
    # a winner would silently retag posts.
    seen, unique, dropped = set(), [], []
    for entry in entries:
        if entry["name"] in seen:
            dropped.append(entry["name"])
            continue
        seen.add(entry["name"])
        unique.append(entry)

    collisions = {}
    for entry in unique:
        collisions.setdefault(entry["name"].lower(), []).append(entry["name"])
    for variants in collisions.values():
        if len(variants) > 1:
            print(f"  note: tags differing only by case: {', '.join(variants)}")

    ordered = sorted(unique, key=lambda e: sort_key(e["name"]))

    # Nothing may disappear in the course of a reordering.
    if {e["name"] for e in ordered} != {e["name"] for e in entries}:
        print("Tag names changed during sorting -- refusing to write.")
        return 1

    body = yaml.dump(
        {"tags": ordered},
        Dumper=IndentedDumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=4096,
    )

    if body == raw:
        print(f"{len(ordered)} tags, already in order. Nothing to do.")
        return 0

    TAGS_FILE.write_text(body, encoding="utf-8")
    moved = sum(1 for a, b in zip(entries, ordered) if a["name"] != b["name"])
    print(f"Sorted {len(ordered)} tags ({moved} moved).")
    if dropped:
        print(f"Removed {len(dropped)} exact duplicate(s): {', '.join(dropped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

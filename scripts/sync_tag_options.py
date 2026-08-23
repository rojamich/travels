#!/usr/bin/env python3
"""
sync_tag_options.py — write the tag list into admin/config.yml
=============================================================================
Why the tag picker stopped being a relation widget
--------------------------------------------------
A relation widget fetches its options at the moment the field is focused —
here, _data/tags.yml through Git Gateway. Typing before that fetch lands
filters an empty list, and when the response arrives the widget re-renders
and throws the query away. What the editor sees is: type "Baz", the list
blanks, reloads, and comes back at A with nothing filtered. The second tag
on the same post works, because by then the options are cached.

No relation setting fixes that; it is a load race, not a missing option. So
the options ship inside admin/config.yml instead, as a plain select widget.
Nothing to fetch means nothing to race, and filtering works on the first
keystroke.

_data/tags.yml stays the source of truth. This script copies it into the
config, the same way sync_trip_filters.py maintains the trip filter buttons.

WHAT IT TOUCHES
    Only the lines between the BEGIN/END marker comments in admin/config.yml.
    There is one marker pair per tag field (posts and trips); both get the
    same list. Nothing outside the markers is read or rewritten, and the
    result is parsed as YAML before it is saved.

Run it by hand:

    python scripts/sync_tag_options.py

It also runs automatically in GitHub Actions whenever _data/tags.yml changes
on main (see .github/workflows/sort-tags.yml).

Exit codes: 0 = config is up to date (whether or not it needed changing),
            1 = something was wrong and nothing was written.
"""

import sys
from pathlib import Path

import yaml

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parent.parent
TAGS_FILE = ROOT / "_data" / "tags.yml"
CONFIG = ROOT / "admin" / "config.yml"

INDENT = " " * 10
BEGIN = f"{INDENT}# --- BEGIN generated tag options (scripts/sync_tag_options.py) ---"
END = f"{INDENT}# --- END generated tag options ---"

# Characters that would change how YAML reads a plain scalar. A tag holding
# one gets quoted rather than trusted.
NEEDS_QUOTING = set(":#{}[],&*!|>'\"%@`")


def as_yaml_scalar(name):
    if name != name.strip() or not name:
        return None  # caller reports it; padded names are a data bug
    if any(c in NEEDS_QUOTING for c in name) or name[0] == "-":
        escaped = name.replace('"', '\\"')
        return f'"{escaped}"'
    return name


def main():
    try:
        data = yaml.safe_load(TAGS_FILE.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"Could not read {TAGS_FILE}: {exc}")
        return 1

    if not isinstance(data, dict) or not isinstance(data.get("tags"), list):
        print("Expected a top-level 'tags:' list in _data/tags.yml.")
        return 1

    names = []
    for entry in data["tags"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            print(f"Skipping malformed entry: {entry!r}")
            return 1
        names.append(entry["name"])

    lines = [BEGIN]
    for name in names:
        scalar = as_yaml_scalar(name)
        if scalar is None:
            print(f"Tag {name!r} is empty or padded with spaces — fix it in "
                  f"_data/tags.yml first. Nothing written.")
            return 1
        lines.append(f"{INDENT}- {scalar}")
    lines.append(END)
    block = "\n".join(lines)

    original = CONFIG.read_text(encoding="utf-8")
    if BEGIN not in original or END not in original:
        print("error: the marker comments are missing from admin/config.yml.\n"
              "Each tag field's `options:` needs these two lines under it:\n"
              f"{BEGIN}\n{END}")
        return 1

    # Rebuild every marked block. There is one per tag field, and they must
    # not drift apart, so all of them are written from the same list.
    out, rest, blocks = [], original, 0
    while BEGIN in rest:
        head, rest = rest.split(BEGIN, 1)
        if END not in rest:
            print("error: a BEGIN marker has no matching END.")
            return 1
        _, rest = rest.split(END, 1)
        out.append(head)
        out.append(block)
        blocks += 1
    out.append(rest)
    updated = "".join(out)

    try:
        yaml.safe_load(updated)
    except yaml.YAMLError as exc:
        print(f"Refusing to write: the result is not valid YAML.\n  {exc}")
        return 1

    if updated == original:
        print(f"{len(names)} tags across {blocks} field(s) — already up to date.")
        return 0

    CONFIG.write_text(updated, encoding="utf-8")
    print(f"Wrote {len(names)} tag options into {blocks} field(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

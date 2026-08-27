#!/usr/bin/env python3
"""
sync_country_options.py — write the country list into admin/config.yml
=============================================================================
Why this exists
---------------
A trip names its countries through a select widget in the editor, and Decap
CMS cannot fill a select from a data file — the options have to be spelled
out in admin/config.yml. So there were two country lists: the real one in
_data/countries.yml, and a hand-typed list of 199 names in the config.

They drifted, in both directions and silently:

  * 123 countries could be picked that _data/countries.yml had never heard
    of. Picking one looked fine in the editor and then quietly failed — no
    ISO code meant no shading on the world map, and no continent meant no
    contribution to the continent tally on /stats/.
  * 20 places that WERE in _data/countries.yml — Puerto Rico, Hong Kong,
    Greenland, Kosovo, Palestine among them — were missing from the picker,
    and a select widget offers no way to type a value it doesn't list.

This script makes the picker a copy of the real list instead, the same way
sync_tag_options.py does for tags. _data/countries.yml stays the source of
truth; nothing here decides anything.

WHAT IT TOUCHES
    Only the lines between the BEGIN/END marker comments in admin/config.yml.
    Nothing outside them is read or rewritten, and the result is parsed as
    YAML before it is saved.

Run it by hand:

    python scripts/sync_country_options.py

It also runs automatically in GitHub Actions whenever _data/countries.yml
changes on main (see .github/workflows/sync-country-options.yml).

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
COUNTRIES_FILE = ROOT / "_data" / "countries.yml"
CONFIG = ROOT / "admin" / "config.yml"

INDENT = " " * 14
BEGIN = f"{INDENT}# --- BEGIN generated country options (scripts/sync_country_options.py) ---"
END = f"{INDENT}# --- END generated country options ---"

# Characters that would change how YAML reads a plain scalar. A name holding
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
        data = yaml.safe_load(COUNTRIES_FILE.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"Could not read {COUNTRIES_FILE}: {exc}")
        return 1

    if not isinstance(data, list) or not data:
        print("Expected a top-level list of country records in _data/countries.yml.")
        return 1

    names = []
    for entry in data:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            print(f"Skipping malformed record: {entry!r}")
            return 1
        names.append(entry["name"])

    # Alphabetical, because that is the order she reads them in. The data file
    # is grouped by continent, which is the right order for editing it and the
    # wrong one for finding "Portugal" in a dropdown.
    names.sort(key=lambda n: n.lower())

    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        print("Refusing to write: _data/countries.yml lists these names twice "
              f"— {', '.join(duplicates)}. Two records with one name make the "
              "alias table ambiguous.")
        return 1

    lines = [BEGIN]
    for name in names:
        scalar = as_yaml_scalar(name)
        if scalar is None:
            print(f"Country {name!r} is empty or padded with spaces — fix it in "
                  f"_data/countries.yml first. Nothing written.")
            return 1
        lines.append(f"{INDENT}- {scalar}")
    lines.append(END)
    block = "\n".join(lines)

    original = CONFIG.read_text(encoding="utf-8")
    if BEGIN not in original or END not in original:
        print("error: the marker comments are missing from admin/config.yml.\n"
              "The country field's `options:` needs these two lines under it:\n"
              f"{BEGIN}\n{END}")
        return 1

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
        print(f"{len(names)} countries across {blocks} field(s) — already up to date.")
        return 0

    CONFIG.write_text(updated, encoding="utf-8")
    print(f"Wrote {len(names)} country options into {blocks} field(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
sync_state_options.py — write the US state list into admin/config.yml
=============================================================================
Why this exists
---------------
A trip's `states:` used to be free text. /stats/ counts those names and the
US coverage map shades them by matching the map's own spelling, so a typed
"CA" or "new york" would count in the States tile and shade nothing — two
figures that disagree, which is the one thing the stats keep getting wrong.

The editor now offers a picker instead. Decap can't fill a select from a
file, so the names are written into admin/config.yml, the same way
sync_country_options.py does for countries. The source is the map itself,
assets/data/us-states.geo.json: whatever can be picked is, by construction,
a shape the map can shade.

The map also has District of Columbia and Puerto Rico. Neither is one of the
50 states the "of 50" headline counts, and Puerto Rico is already a country
in _data/countries.yml, so both are left out on purpose (NOT_STATES below).

WHAT IT TOUCHES
    Only the lines between each pair of BEGIN/END marker comments in
    admin/config.yml — the trip's states picker and the state flag picker.
    Each block keeps the indentation of its own marker. The result is parsed
    as YAML before it is saved.

    python scripts/sync_state_options.py

The list of states does not change, so there is no CI job for this; run it
if assets/data/us-states.geo.json is ever replaced.

Exit codes: 0 = config is up to date (whether or not it needed changing),
            1 = something was wrong and nothing was written.
"""

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GEO = ROOT / "assets" / "data" / "us-states.geo.json"
CONFIG = ROOT / "admin" / "config.yml"

NOT_STATES = {"District of Columbia", "Puerto Rico"}
BEGIN_RE = re.compile(r"^( *)# --- BEGIN generated state options \(scripts/sync_state_options\.py\) ---$")
END_TEXT = "# --- END generated state options ---"


def main():
    names = sorted({f["properties"]["name"].strip()
                    for f in json.loads(GEO.read_text(encoding="utf-8"))["features"]} - NOT_STATES)
    if len(names) != 50:
        print(f"Expected 50 states in {GEO.name}, found {len(names)}. Nothing written.")
        return 1

    raw = CONFIG.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")

    out, blocks, i = [], 0, 0
    while i < len(lines):
        m = BEGIN_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        indent = m.group(1)
        out.append(lines[i])
        j = i + 1
        while j < len(lines) and lines[j].strip() != END_TEXT:
            j += 1
        if j == len(lines) or not lines[j].startswith(indent + "#"):
            print(f"BEGIN marker on line {i + 1} has no matching END. Nothing written.")
            return 1
        out.extend(f"{indent}- {n}" for n in names)
        out.append(lines[j])
        blocks += 1
        i = j + 1

    if blocks == 0:
        print("No generated state option markers found in admin/config.yml. Nothing written.")
        return 1

    new = "\n".join(out)
    try:
        yaml.safe_load(new)
    except yaml.YAMLError as exc:
        print(f"The result would not be valid YAML ({exc}). Nothing written.")
        return 1

    if new == raw.replace("\r\n", "\n"):
        print(f"{len(names)} states across {blocks} field(s) — already up to date.")
        return 0
    CONFIG.write_bytes(new.replace("\n", nl).encode("utf-8"))
    print(f"{len(names)} states written into {blocks} field(s) in admin/config.yml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

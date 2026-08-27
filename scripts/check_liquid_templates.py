#!/usr/bin/env python3
"""
check_liquid_templates.py — render the fragile templates before pushing
=============================================================================
Why this exists
---------------
A deploy failed with:

    Liquid Exception: Liquid error (_includes/upkeep-data.html line 142):
    Cannot sort a null object.

The cause was a trip created in the editor that had no posts yet. Jekyll's
`sort` raises on nil rather than returning nothing, so one empty trip took the
whole site down — every page, not just the one with the bug.

Nothing had rendered that template before Netlify did. This does, against the
shapes that break it: no posts, no data files, a brand-new empty trip.

WHAT IT IS AND ISN'T
It uses python-liquid, not Jekyll, so it is an approximation: it will not catch
a Jekyll-specific filter behaving differently, and it does not know about the
site's real content. What it does catch is the class of bug above — a template
that works on today's data and explodes on an empty or missing value — which is
the class that has actually broken this site.

The real check is still the Netlify build. This one just runs in two seconds,
before the push, instead of two minutes after it.

    pip install python-liquid
    python scripts/check_liquid_templates.py

Exit codes: 0 = every template rendered against every fixture
            1 = one of them raised, with the fixture named
"""

import re
import sys
from pathlib import Path

try:
    from liquid import Environment, Undefined
except ImportError:
    print("python-liquid is not installed — pip install python-liquid")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent

# Templates that compute rather than just display, and so have somewhere to go
# wrong. Each is rendered on its own, with `include` tags stripped: this checks
# one file's logic, not the whole page.
TEMPLATES = [
    "_includes/upkeep-data.html",
]


def jekyll_sort(value, key=None):
    """Jekyll's `sort`, including the part that raises on nil."""
    if value is None or isinstance(value, Undefined):
        raise ValueError("Cannot sort a null object.")
    if key:
        return sorted(value, key=lambda item: (item or {}).get(key) or 0)
    return sorted(value)


def build_env():
    env = Environment()
    env.filters["sort"] = jekyll_sort
    env.filters["push"] = lambda arr, item: list(arr) + [item]
    env.filters["relative_url"] = lambda v="", *a, **k: v
    env.filters["absolute_url"] = lambda v="", *a, **k: v
    env.filters["jsonify"] = lambda v=None, *a, **k: v
    env.filters["strip_html"] = lambda v="", *a, **k: v
    env.filters["normalize_whitespace"] = lambda v="", *a, **k: v
    env.filters["date_to_xmlschema"] = lambda v="", *a, **k: v
    return env


POST = {"title": "A day", "url": "/a-day/", "location": {"lat": 1}, "order": 1}
POST_NO_LOCATION = {"title": "A letter home", "url": "/letter/", "location": {}, "order": 2}

# The shapes that have broken a build, or could.
FIXTURES = {
    "an ordinary site": {
        "trips": [{"title": "Iceland", "slug": "iceland"}],
        "categories": {"iceland": [POST, POST_NO_LOCATION]},
        "data": {"records": {"entries": [{"title": "Most steps", "value": "42,382"}]},
                 "country_images": {"entries": [{"name": "Iceland", "url": "http://x/y.png"}]},
                 "country_aliases": {"Iceland": "Iceland"},
                 "status": {"current_location": "Yerevan, Armenia"},
                 "nights": {"stray_day_trips": []},
                 "freshness": {"status": {"days": 5, "date": "1 August 2026"}}},
    },
    "a brand-new trip with no posts": {
        "trips": [{"title": "City of Empires", "slug": "city-of-empires"}],
        "categories": {},
        "data": {"records": None, "country_images": None, "country_aliases": {},
                 "status": {}, "nights": {}, "freshness": {}},
    },
    "no data files at all": {
        "trips": [], "categories": {},
        "data": {"records": None, "country_images": None, "country_aliases": None,
                 "status": None, "nights": None, "freshness": None},
    },
    "a stale status bar and a stray day trip": {
        "trips": [{"title": "Iceland", "slug": "iceland"}],
        "categories": {"iceland": [POST_NO_LOCATION]},
        "data": {"records": {"entries": [{"title": "Hottest day", "value": ""}]},
                 "country_images": {"entries": [{"name": "Nowhere", "url": "http://x/y.png"}]},
                 "country_aliases": {"Iceland": "Iceland"},
                 "status": {"current_location": "Yerevan, Armenia", "next_destination": "Istanbul"},
                 "nights": {"stray_day_trips": [{"post": "A Day Trip", "url": "/d/",
                                                 "trip": "Iceland", "country": "Botswana"}]},
                 "freshness": {"status": {"days": 90, "date": "1 May 2026"}}},
    },
}


def main():
    env = build_env()
    failures = 0

    for rel in TEMPLATES:
        path = ROOT / rel
        source = path.read_text(encoding="utf-8")
        source = re.sub(r"^---\n.*?\n---\n", "", source, flags=re.S)
        source = re.sub(r"\{%-?\s*include\s+[^%]*%\}", "", source)
        # Render the computed list too, so a broken row is caught, not just a
        # broken assignment.
        template = env.from_string(source + "{% for row in upkeep %}<ROW>{{ row }}</ROW>{% endfor %}")

        for label, fixture in FIXTURES.items():
            context = {
                "visited_countries": ["Iceland"],
                "site": {"posts": [POST, POST_NO_LOCATION],
                         "trips": fixture["trips"],
                         "categories": fixture["categories"],
                         "data": fixture["data"]},
            }
            try:
                out = template.render(**context)
                rows = len(re.findall(r"<ROW>", out))
                print(f"  ok    {rel} — {label} ({rows} item(s))")
            except Exception as exc:  # noqa: BLE001 - report anything at all
                failures += 1
                print(f"  FAIL  {rel} — {label}")
                print(f"        {type(exc).__name__}: {exc}")

    if failures:
        print(f"\n{failures} render(s) failed. Netlify would fail the same way.")
        return 1
    print("\nEvery template rendered against every fixture.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

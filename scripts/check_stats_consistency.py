#!/usr/bin/env python3
"""
check_stats_consistency.py — do the built pages agree with each other?
=============================================================================
Why this exists
---------------
Most of what /stats/ shows is said twice: the Countries tile and the world
map headline, the continent cards and the Continents tile, the "Days on
trips" tile and the day counts in the "By trip" list, the nights bars and the
countries visited, the "Most countries in one year" record and that year's
own page. Every time two of those have disagreed on this site, it was two
pieces of code with their own copy of a rule, and nobody noticed until a
reader could.

This reads the pages the real build produced and checks each pair. It does
NOT re-implement any rule — a Python copy of "which countries count" would be
one more copy to drift. It only asks whether the site agrees with itself, so
it cannot be wrong in the same way the templates are.

    python scripts/check_stats_consistency.py                  # the live site
    python scripts/check_stats_consistency.py <deploy-preview-url>

Run it against a deploy preview before merging anything that touches
_includes/country-data.html, trip-countries.html, trips-in-year.html,
canon-country.html, _pages/stats.html, _layouts/year.html, _plugins/nights.rb
or _data/countries.yml.

Exit codes: 0 = everything agrees, 1 = something doesn't (each one named).
"""
import html
import re
import sys
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else
        "https://where-in-the-world-are-mike-and-jen.netlify.app").rstrip("/")

passed, failed = 0, 0


def get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "stats-consistency-check"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def check(name, got, want):
    global passed, failed
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}" + ("" if ok else f"\n          got {got!r}, want {want!r}"))
    if ok:
        passed += 1
    else:
        failed += 1


def num(s):
    return int(re.sub(r"[^\d]", "", s) or 0)


stats = get("/stats/")
tiles = {text(l): text(v) for v, l in re.findall(
    r'class="stat-value">(.*?)</div>\s*<div class="stat-label">(.*?)</div>', stats, re.S)}
countries = num(tiles.get("Countries visited", "0"))
continents = num(tiles.get("Continents", "0"))
trips_tile = num(tiles.get("Trips taken", "0"))
days_tile = num(tiles.get("Days on trips", "0"))
print(f"/stats/ at {BASE}: {countries} countries, {continents} continents, "
      f"{trips_tile} trips, {days_tile} days")

# ---------------------------------------------------------------- continents
print("\ncountries by continent")
cards = re.findall(r'<section class="cont-group">(.*?)</section>', stats, re.S)
card_rows = []
for c in cards:
    name = text(re.search(r'class="cont-name">(.*?)</span>', c, re.S).group(1))
    n = num(re.search(r'class="cont-count"[^>]*>(.*?)</span>', c, re.S).group(1))
    chips = [text(x) for x in re.findall(r'<span class="country-chip">(.*?)</span>', c, re.S)]
    card_rows.append((name, n, chips))
real = [r for r in card_rows if r[0] != "Somewhere else"]
check("one card per continent the Continents tile counts", len(real), continents)
check("the cards add up to the Countries tile", sum(n for _, n, _ in card_rows), countries)
check("each card's number is the countries listed in it",
      [n for _, n, _ in card_rows], [len(ch) for _, _, ch in card_rows])
all_chips = [c for _, _, ch in card_rows for c in ch]
check("no country appears in two cards", len(all_chips), len(set(all_chips)))
check("biggest card first", [n for _, n, _ in real], sorted((n for _, n, _ in real), reverse=True))
check("nothing is filed under 'Somewhere else'", [r[2] for r in card_rows if r[0] == "Somewhere else"], [])
cards_line = re.search(r'id="countries-by-continent".*?<strong>(\d+)</strong>.*?<strong>(\d+)</strong>', stats, re.S)
check("the section's own sentence matches the tiles",
      cards_line and (int(cards_line.group(1)), int(cards_line.group(2))), (countries, continents))

# ---------------------------------------------------------------- world map
print("\nworld map")
m = re.search(r"<strong>(\d+)</strong> of ~(\d+) countries visited", stats)
check("the map headline says the same number as the tile", m and int(m.group(1)), countries)
codes = re.search(r"var VISITED = (\[.*?\]);", stats, re.S)
n_codes = len(re.findall(r'"[A-Z]{3}"', codes.group(1))) if codes else -1
check("one shaded shape per country, at most", n_codes <= countries, True)

# ---------------------------------------------------------------- nights
print("\nnights")
m = re.search(r"<strong>(\d+)</strong> nights across\s*<strong>(\d+)</strong> countries and\s*"
              r"<strong>(\d+)</strong> continents", stats)
if m:
    nights_total, night_countries, night_conts = map(int, m.groups())
    blocks = re.split(r'<h3 class="nights-sub">', stats)
    def bars(title):
        for b in blocks:
            if b.startswith(title):
                return [(text(n), num(v)) for n, v in re.findall(
                    r'class="nights-label">(.*?)</div>.*?class="nights-value">(\d+)', b, re.S)]
        return []
    by_cont, by_country = bars("By continent"), bars("By country")
    check("the continent bars add up to the nights total", sum(v for _, v in by_cont), nights_total)
    check("the country bars add up to the nights total", sum(v for _, v in by_country), nights_total)
    check("one bar per country the sentence counts", len(by_country), night_countries)
    check("one bar per continent the sentence counts", len(by_cont), night_conts)
    d = re.search(r'class="nights-daytrip">\s*<strong>(\d+)</strong>.*?—\s*(.*?)\.\s*</p>', stats, re.S)
    day_only = [x.strip() for x in text(d.group(2)).split(",")] if d else []
    night_names = {n for n, _ in by_country}
    check("countries with nights + countries without = the Countries tile",
          night_countries + len(day_only), countries)
    check("a country is never in both", sorted(night_names & set(day_only)), [])
    check("and together they are exactly the countries in the cards",
          sorted(night_names | set(day_only)), sorted(all_chips))
    check("nights continents are among the continents visited",
          sorted({n for n, _ in by_cont} - {r[0] for r in real}), [])
else:
    print("  (no nights section on the page)")
    nights_total = None

# ---------------------------------------------------------------- by trip
print("\nby trip")
rows = re.findall(r'<a href="[^"]*" class="stats-trip-row">(.*?)</a>', stats, re.S)
check("one row per trip the Trips tile counts", len(rows), trips_tile)
day_rows = [num(x) for x in re.findall(r"(\d[\d,]*) days", " ".join(text(r) for r in rows))]
check("the rows' days add up to the Days on trips tile", sum(day_rows), days_tile)
if nights_total is not None:
    check("days minus nights is one per trip (the travel day home)", days_tile - nights_total, len(day_rows))

# ---------------------------------------------------------------- states
us = num(tiles.get(next((k for k in tiles if k.startswith("States")), ""), "0"))
if us:
    print("\nUS states")
    m = re.search(r"<strong>(\d+)</strong> of 50 states visited", stats)
    check("the states headline matches the tile", m and int(m.group(1)), us)
    chips = re.findall(r'class="country-chip country-chip--state">', stats)
    check("one chip per state counted", len(chips), us)
    m = re.search(r"var VISITED_STATES = (\[.*?\]);", stats, re.S)
    names = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    check("the map is given the same states, once each ignoring case",
          len({n.lower() for n in names}), us)

# ---------------------------------------------------------------- years
print("\nyear pages")
card_set = set(all_chips)
best = re.search(r"Most countries in one year.*?record-value\">(\d+).*?record-meta\">(\d{4})[^<]*<"
                 r".*?record-countries\">(.*?)</div>", stats, re.S)
# Every year page the build made, from the sitemap; the links on /stats/ only
# reach the best year.
try:
    years = sorted({int(y) for y in re.findall(r"/year/(\d{4})/", get("/sitemap.xml"))})
except Exception:                                  # noqa: BLE001
    years = []
years = years or sorted({int(y) for y in re.findall(r'href="/year/(\d{4})/"', stats)})
if best:
    years = sorted(set(years) | {int(best.group(2))})
top = (0, None)
for y in years:
    try:
        page = get(f"/year/{y}/")
    except Exception as exc:                       # noqa: BLE001
        check(f"/year/{y}/ exists", str(exc), "a page")
        continue
    stat = re.search(r'<div class="v">(\d+)</div><div class="l">Countries</div>', page)
    chips = [text(x) for x in re.findall(r'<span class="country-chip">(.*?)</span>',
                                        page.split('class="year-countries"')[-1].split("</div>")[0])]
    n = int(stat.group(1)) if stat else -1
    check(f"/year/{y}/ counts the countries it lists ({n})", n, len(chips))
    check(f"/year/{y}/ lists only countries /stats/ counts", sorted(set(chips) - card_set), [])
    if n > top[0]:
        top = (n, y, chips)
if best:
    check("'Most countries in one year' is the year page with the most",
          (int(best.group(1)), int(best.group(2))), (top[0], top[1]))
    listed = [x.strip() for x in text(best.group(3)).split("·")]
    check("and names the same countries that page lists", sorted(listed), sorted(top[2]))

# ---------------------------------------------------------------- admin
print("\n/admin-stats/")
try:
    admin = get("/admin-stats/")
    m = re.search(r"<strong>(\d+)</strong> countries counted, from", admin)
    check("the country audit counts the same countries", m and int(m.group(1)), countries)
except Exception as exc:                           # noqa: BLE001
    print(f"  (could not read it: {exc})")

print(f"\n{passed} agree, {failed} don't")
sys.exit(1 if failed else 0)

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
territories = num(next((v for k, v in tiles.items() if k.startswith("Territor")), "0"))
continents = num(tiles.get("Continents", "0"))
trips_tile = num(tiles.get("Trips taken", "0"))
days_tile = num(tiles.get("Days on trips", "0"))
print(f"/stats/ at {BASE}: {countries} countries, {territories} territories, {continents} continents, "
      f"{trips_tile} trips, {days_tile} days")

# ---------------------------------------------------------------- continents
print("\ncountries by continent")
cards = re.findall(r'<section class="cont-group">(.*?)</section>', stats, re.S)
CHIP = r'<span class="country-chip">(?:<img[^>]*>)?(.*?)</span>'
TERR_CHIP = r'<span class="country-chip country-chip--territory">(?:<img[^>]*>)?(.*?)<span class="chip-tag">'
card_rows, terr_rows = [], []
for c in cards:
    name = text(re.search(r'class="cont-name">(.*?)</span>', c, re.S).group(1))
    badge = re.search(r'class="cont-count"[^>]*>(.*?)</span>', c, re.S)
    plus = re.search(r'class="cont-terr">\+(\d+)', c)
    chips = [text(x) for x in re.findall(CHIP, c, re.S)]
    terrs = [text(x) for x in re.findall(TERR_CHIP, c, re.S)]
    card_rows.append((name, num(badge.group(1)) if badge else 0, chips))
    terr_rows.append((name, int(plus.group(1)) if plus else 0, terrs))
real = [r for r in card_rows if r[0] != "Somewhere else"]
check("one card per continent the Continents tile counts", len(real), continents)
check("the badges add up to the Countries tile", sum(n for _, n, _ in card_rows), countries)
check("each badge is the countries in its card",
      [n for _, n, _ in card_rows], [len(ch) for _, _, ch in card_rows])
check("the territory chips add up to the Territories tile",
      sum(len(t) for _, _, t in terr_rows), territories)
check("each card's '+N territory' is the territories in it",
      [n for _, n, _ in terr_rows], [len(t) for _, _, t in terr_rows])
all_chips = [c for _, _, ch in card_rows for c in ch] + [t for _, _, ts in terr_rows for t in ts]
check("no country appears in two cards", len(all_chips), len(set(all_chips)))
check("most countries first", [n for _, n, _ in real], sorted((n for _, n, _ in real), reverse=True))
check("nothing is filed under 'Somewhere else'", [r[2] for r in card_rows if r[0] == "Somewhere else"], [])
line = re.search(r'id="countries-by-continent".*?</p>', stats, re.S)
nums = [int(x) for x in re.findall(r"<strong>(\d+)</strong>", line.group(0))] if line else []
check("the section's own sentence matches the tiles",
      nums, [countries] + ([territories] if territories else []) + [continents])

# ---------------------------------------------------------------- world map
print("\nworld map")
m = re.search(r"<strong>(\d+)</strong> of ~?(\d+) countries visited", stats)
check("the map headline says the same number as the tile", m and int(m.group(1)), countries)
check("out of 195 countries, counted from _data/countries.yml", m and int(m.group(2)), 195)
if territories:
    t = re.search(r"countries visited,\s*plus <strong>(\d+)</strong> territor", stats)
    check("and names the territories separately", t and int(t.group(1)), territories)
codes = re.search(r"var VISITED = (\[.*?\]);", stats, re.S)
n_codes = len(re.findall(r'"[A-Z]{3}"', codes.group(1))) if codes else -1
check("one shaded shape per place, at most", n_codes <= countries + territories, True)

# ---------------------------------------------------------------- nights
print("\nnights")
m = re.search(r"<strong>(\d+)</strong> nights across\s*<strong>(\d+)</strong> countr(?:y|ies),\s*"
              r"(?:<strong>(\d+)</strong> territor(?:y|ies) and\s*)?<strong>(\d+)</strong> continents", stats)
if m:
    nights_total = int(m.group(1))
    night_countries = int(m.group(2)) + int(m.group(3) or 0)
    night_conts = int(m.group(4))
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
    check("one bar per country and territory the sentence counts", len(by_country), night_countries)
    check("one bar per continent the sentence counts", len(by_cont), night_conts)
    d = re.search(r'class="nights-daytrip">(.*?)—\s*(.*?)\.\s*</p>', stats, re.S)
    day_only = [x.strip() for x in text(d.group(2)).split(",")] if d else []
    check("the day-trip sentence counts the places it names",
          sum(int(x) for x in re.findall(r"<strong>(\d+)</strong>", d.group(1))) if d else 0,
          len(day_only))
    night_names = {n for n, _ in by_country}
    check("places with nights + places without = countries + territories",
          night_countries + len(day_only), countries + territories)
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
    tstat = re.search(r'<div class="v">(\d+)</div><div class="l">Territor', page)
    block = page.split('class="year-countries"')[-1].split("</div>")[0]
    chips = [text(x) for x in re.findall(r'<span class="country-chip">(.*?)</span>', block)]
    terrs = [text(x) for x in re.findall(
        r'<span class="country-chip country-chip--territory">(.*?)<span', block)]
    n = int(stat.group(1)) if stat else -1
    check(f"/year/{y}/ counts the countries it lists ({n})", n, len(chips))
    check(f"/year/{y}/ counts the territories it lists", int(tstat.group(1)) if tstat else 0, len(terrs))
    check(f"/year/{y}/ lists only places /stats/ counts", sorted(set(chips + terrs) - card_set), [])
    if n > top[0]:
        top = (n, y, chips)
if best:
    check("'Most countries in one year' is the year page with the most",
          (int(best.group(1)), int(best.group(2))), (top[0], top[1]))
    listed = [x.strip() for x in text(best.group(3)).split("— plus")[0].split("·")]
    check("and names the same countries that page lists", sorted(listed), sorted(top[2]))

# ---------------------------------------------------------------- admin
print("\n/admin-stats/")
try:
    admin = get("/admin-stats/")
    m = re.search(r"<strong>(\d+)</strong> countries(?: and <strong>(\d+)</strong> "
                  r"territor(?:y|ies))? counted, from", admin)
    check("the country audit counts the same countries and territories",
          m and (int(m.group(1)), int(m.group(2) or 0)), (countries, territories))
except Exception as exc:                           # noqa: BLE001
    print(f"  (could not read it: {exc})")

print(f"\n{passed} agree, {failed} don't")
sys.exit(1 if failed else 0)

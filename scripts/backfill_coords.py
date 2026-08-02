#!/usr/bin/env python3
"""
backfill_coords.py — add map coordinates to posts that are missing them.

Each entry below was inferred from the post's own text (landmarks, city
names, restaurants, trip context). Confidence is recorded alongside so the
reasoning is auditable later; posts we couldn't place confidently are
deliberately absent and stay blank for a human to fill in.

Only touches posts that currently have NO lat. Never overwrites an existing
coordinate. Idempotent — safe to re-run.

Usage:
    python scripts/backfill_coords.py --dry-run
    python scripts/backfill_coords.py
"""

import argparse
import io
import os
import re
import sys

# file stem -> (place name, lat, lng, confidence, why)
COORDS = {
    # ---------------- European Excursion (2022) ----------------
    "2022-02-09-fish-chips-embarrassment-and-a-little-murder": (
        "Whitechapel, London", 51.5194, -0.0611, "high",
        "Says 'our first stop in London', took the tube to Whitechapel for a Jack the Ripper walking tour."),
    "2022-02-19-a-bus-ride-a-gorgeous-hotel-room-and-french-fries": (
        "Paris, France", 48.8566, 2.3522, "high",
        "Four-hour bus from Belgium to France, then a metro to the room — Paris is the trip's France stop."),
    "2022-02-19-a-new-hat-some-macarons-and-fl-ner": (
        "Paris, France", 48.8566, 2.3522, "high",
        "Hunting for a French beret 'the moment we arrived in France', plus macarons. Same day as the Paris arrival post."),
    "2022-02-19-one-of-my-favorite-topics-food": (
        "Paris, France", 48.8566, 2.3522, "medium",
        "Same date as the other two Paris posts; mentions a cafe, baguette and 'La Bucherie' (a Paris restaurant name)."),
    "2022-02-28-food-more-food": (
        "Florence, Italy", 43.7696, 11.2558, "high",
        "Cannoli 'invented in Florence' from a bakery near their Airbnb; date lines up with the Florence run of posts."),
    "2022-03-10-world-famous-beerhall-wrapping-up-our-walking-tour": (
        "Munich, Germany", 48.1351, 11.5820, "medium",
        "The 'world's most famous' beerhall on an audio tour is Hofbrauhaus in Munich. Could be another Bavarian hall, hence medium."),
    "2022-05-14-gothic-style-architecture": (
        "Nuremberg, Germany", 49.4521, 11.0767, "high",
        "Explicitly 'as we toured Nuremburg', and names the Fleischbrucke bridge there."),
    "2022-06-24-an-emotional-toll-taken-during-the-city-tour": (
        "Berlin, Germany", 52.5139, 13.3778, "high",
        "Memorial to the Murdered Jews of Europe — Berlin. Coords are the memorial itself."),
    "2022-11-13-checking-off-two-bucket-list-items": (
        "Amsterdam, Netherlands", 52.3676, 4.9041, "medium",
        "Windmill within biking distance of their BnB, dodging cyclists — Netherlands leg. Exact town unknown, so Amsterdam stands in."),
    "2022-11-13-our-journey-home": (
        "Amsterdam, Netherlands", 52.3676, 4.9041, "high",
        "'I do not love the process to get from Amsterdam to London' — written departing Amsterdam."),

    # ---------------- New Zealand (2022) ----------------
    "2022-11-18-holy-travels-batman": (
        "Eugene, Oregon", 44.0521, -123.0868, "high",
        "Travel day that starts at 'our tiny Eugene airport' with a 4-hour flight to Dallas."),
    "2022-11-18-15-hours-later": (
        "Auckland, New Zealand", -36.8485, 174.7633, "medium",
        "Arrival post after the long-haul flight. Auckland is the standard NZ international entry point."),
    "2022-11-18-fl-ner-driving-on-the-left-hand-side": (
        "Auckland, New Zealand", -36.8485, 174.7633, "low",
        "Rental car and a 'coastal, downtown area' on their first NZ days. Placed near Auckland but the town is never named."),
    "2022-11-23-beach-day": (
        "Hot Water Beach, Coromandel", -36.8886, 175.8206, "high",
        "Names Cooks Beach / Hot Springs Beach on the Coromandel Peninsula."),
    "2022-11-23-day-two-in-new-zealand": (
        "Matamata (Hobbiton), New Zealand", -37.8721, 175.6829, "medium",
        "'We did the beach trip and Hobbiton in one day' — Hobbiton is at Matamata."),
    "2022-12-03-lake-hike": (
        "Queenstown, New Zealand", -45.0312, 168.6626, "medium",
        "Run around a lake through a hilly neighbourhood; the next post confirms they were lakeside in Queenstown."),
    "2022-12-04-time-for-a-campervan-adventure": (
        "Queenstown, New Zealand", -45.0312, 168.6626, "high",
        "'One last run in down by the lake of Queenstown' before collecting the campervan."),
    "2022-12-13-traveling-home": (
        "Queenstown, New Zealand", -45.0312, 168.6626, "high",
        "'We flew from Queenstown to Auckland' — the day starts in Queenstown."),

    # ---------------- European Exploration (2023) ----------------
    "2023-08-03-lazy-sunday": (
        "Bad Homburg, Germany", 50.2271, 8.6161, "medium",
        "A pet-sitting day with the resident cats — matches this trip's Bad Homburg house sit."),

    # ---------------- African Safari (2024) ----------------
    "2024-09-02-day-one-in-africa-part-one": (
        "Cape Town, South Africa", -33.9249, 18.4241, "high",
        "First full day of the South Africa leg, which is based in Cape Town."),
    "2024-09-02-day-one-in-africa-part-two": (
        "Boulders Beach, Simon's Town", -34.1975, 18.4519, "high",
        "'Boulder's bay was our next stop where we got to see penguins' — Boulders Beach."),
    "2024-09-03-hiking-lion-s-head-an-escape-room-and-trying-new-foods": (
        "Lion's Head, Cape Town", -33.9353, 18.3897, "high",
        "Title names the Lion's Head hike in Cape Town."),

    # ---------------- Bamboo & Bulgogi (2024) ----------------
    "2024-12-12-in-transit": (
        "Taipei, Taiwan", 25.0330, 121.5654, "high",
        "'Thursday 12/12 here in Taipei, Taiwan' — written during the layover."),

    # ---------------- Peruvian Passage (2025) ----------------
    "2025-09-13-fishing-for-pirahna-o": (
        "Amazon River, near Iquitos", -3.7437, -73.2516, "medium",
        "Piranha fishing and giant lily pads from the lodge boat on the Amazon; the lodge is reached from Iquitos."),
    "2025-09-23-the-adventure-traveling-home": (
        "Iquitos, Peru", -3.7437, -73.2516, "high",
        "'The lodge boarded us up on the riverboat to bring us back to Iquitos.'"),

    # ---------------- Vietnam (2025-26) ----------------
    "2025-12-24-relaxation-tailor-trip-and-my-new-haircut": (
        "Hoi An, Vietnam", 15.8801, 108.3380, "high",
        "A tailor trip during the Hoi An stretch — Hoi An is the tailoring town, and the preceding post is the move there."),
    "2025-12-27-day-2-of-the-ha-giang-loop": (
        "Ha Giang, Vietnam", 22.8233, 104.9784, "high",
        "Explicitly day 2 of the Ha Giang Loop."),
    "2025-12-28-day-3-just-us-in-the-loop": (
        "Ha Giang, Vietnam", 22.8233, 104.9784, "high",
        "Day 3 of the same loop."),
    "2025-12-29-day-4-the-last-day-on-the-loop": (
        "Ha Giang, Vietnam", 22.8233, 104.9784, "high",
        "Day 4, final day of the same loop."),
    "2025-12-30-barbaard-hanois-train-street": (
        "Hanoi Train Street", 21.0245, 105.8412, "high",
        "Title and body are about Hanoi's train street; coords are the street itself."),
    "2025-12-30-rest-day-and-my-newest-tattoo": (
        "Hanoi, Vietnam", 21.0285, 105.8542, "medium",
        "Rest day sharing a date with the Hanoi train street post, so they were still in Hanoi."),

    # ---------------- Life in the Big City (2026) ----------------
    "2026-06-01-our-new-chapter-traveling-to-the-big-apple": (
        "Newport, Oregon", 44.6368, -124.0534, "medium",
        "Departure day. They describe finishing the lease and the Newport, Oregon rental before flying out."),
    "2026-06-10-massage-khinkali-and-the-book-of-mormon": (
        "New York City", 40.7128, -74.0060, "high",
        "'What a nice way to start off NYC', downtown by subway."),
    "2026-06-11-trapeze-lesson-massive-food-portions-an-escape-room-and-our-friend-tom": (
        "Central Park, New York City", 40.7829, -73.9654, "high",
        "Opens with a run through Central Park."),
    "2026-06-12-morning-in-nyc-on-our-way-to-london": (
        "New York City", 40.7128, -74.0060, "high",
        "Final NYC morning in Central Park before the London flight."),

    # ---------------- Red Coats & Red Buses (2026) ----------------
    "2026-06-13-a-very-long-day-in-london": (
        "London, England", 51.5074, -0.1278, "high",
        "Title is the London arrival day."),
    "2026-06-15-a-three-hour-rick-steves-tour-bahn-mi-and-packing-up": (
        "London, England", 51.5074, -0.1278, "high",
        "Rick Steves walking tour during the London leg."),
    "2026-06-21-touring-west-minster-fish-chips-and-the-imperial-war-museum": (
        "Westminster, London", 51.4995, -0.1248, "high",
        "Westminster and the Imperial War Museum; coords are Westminster."),

    # ---------------- Fjords & Forever (2026) ----------------
    "2026-06-17-the-nobel-peace-center-the-sea": (
        "Oslo, Norway", 59.9139, 10.7522, "high",
        "The Nobel Peace Center is in Oslo."),
    "2026-06-18-the-norwegian-museum-of-cultural-history-the-fram-museum": (
        "Oslo, Norway", 59.9139, 10.7522, "high",
        "Both the Museum of Cultural History and the Fram Museum are on Oslo's Bygdoy peninsula."),
    "2026-06-19-schroders-restaurant-jo-nesbo": (
        "Oslo, Norway", 59.9139, 10.7522, "high",
        "Schroder's is the Oslo restaurant from the Harry Hole novels."),
    "2026-06-20-a-day-of-three-museums": (
        "Oslo, Norway", 59.9139, 10.7522, "high",
        "Three museums in a day, mid-run of the Oslo stretch."),
    "2026-06-23-puffins-beluga-whales-and-kayaking": (
        "Longyearbyen, Svalbard", 78.2232, 15.6267, "medium",
        "Puffins, belugas and dry-suit kayaking; sits between the Svalbard posts."),
    "2026-06-24-hike-through-the-valley-of-a-thousand-rivers-and-waterfalls": (
        "Svalbard, Norway", 78.2232, 15.6267, "high",
        "'So stoked to explore more of Svalbard.'"),
    "2026-06-29-reindeer-hotdogs-norway-advances": (
        "Bergen, Norway", 60.3913, 5.3221, "high",
        "'A brisk and beautiful morning greeted us in Bergen', walking the old town wharf (Bryggen)."),
    "2026-07-02-kjeragbolten-a-bucket-list-hike": (
        "Kjeragbolten, Lysefjord", 59.0344, 6.5936, "high",
        "Title names Kjeragbolten, the boulder wedged above Lysefjord."),
    "2026-07-07-climbing-the-goat-hiking-the-devils-gate-and-the-cold-plunge": (
        "Svolvaer, Lofoten", 68.2340, 14.5686, "high",
        "'Climbing the GOAT' is Svolvaergeita, the Svolvaer Goat, in Lofoten — and the next post is nearby Leknes."),
    "2026-07-10-a-down-day-in-leknes": (
        "Leknes, Lofoten", 68.1475, 13.6118, "high",
        "Title names Leknes."),

    # ---------------- Welcome Home: Tbilisi (2026) ----------------
    "2026-07-14-buses-vans-apple-pie": (
        "Tbilisi, Georgia", 41.7151, 44.8271, "high",
        "'We quickly adapted to the lifestyle in Georgia' — first days living in Tbilisi."),
    "2026-07-18-our-first-week-in-tbilisi": (
        "Tbilisi, Georgia", 41.7151, 44.8271, "high",
        "Title names Tbilisi."),
    "2026-07-20-mother-georgia-the-clock-tower-the-botanical-garden-wine-soft-serve": (
        "Tbilisi, Georgia", 41.7151, 44.8271, "high",
        "Mother Georgia, the crooked clock tower and the Botanical Garden are all Tbilisi."),
    "2026-07-25-cathedrals-basilicas-synagogues-and-the-bazaar": (
        "Old Town, Tbilisi", 41.6938, 44.8015, "high",
        "Gudiashvili Square in the old town; coords are old Tbilisi."),
    "2026-07-25-tbilisi-week-two": (
        "Tbilisi, Georgia", 41.7151, 44.8271, "high",
        "Title names Tbilisi."),
    "2026-07-26-a-hike-to-turtle-lake-jennas-alter-ego": (
        "Turtle Lake, Tbilisi", 41.7093, 44.7564, "high",
        "Turtle Lake sits on the ridge above Tbilisi; the path starts 'right up the hill from us'."),
    "2026-07-28-a-sulphur-bathhouse-bargaining-at-the-bazaar": (
        "Abanotubani, Tbilisi", 41.6893, 44.8090, "high",
        "The sulphur bathhouses are in Abanotubani, Tbilisi's bath district."),
}


def has_coords(front_matter):
    return re.search(r"^\s+lat:\s*[-0-9]", front_matter, re.M) is not None


def split_front_matter(text):
    """Return (front_matter, rest) or (None, None).

    Front matter is delimited by a line that is exactly '---'. A naive
    text.split('---') is wrong here: one post's title contains '---->',
    which would split mid-line and corrupt the file.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None, None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "".join(lines[1:i]), "".join(lines[i:])
    return None, None


def apply_location(front_matter, name, lat, lng):
    """Insert or complete the location block, preserving the file's line endings."""
    nl = "\r\n" if "\r\n" in front_matter else "\n"
    block = (
        f"location:{nl}"
        f"  name: {name}{nl}"
        f"  lat: {lat}{nl}"
        f"  lng: {lng}{nl}"
    )

    # Existing location block (e.g. a name with no coords) — replace wholesale.
    m = re.search(r"^location:\s*\r?\n(?:[ \t]+\S.*\r?\n)*", front_matter, re.M)
    if m:
        return front_matter[: m.start()] + block + front_matter[m.end():]

    # Otherwise append, before any trailing blank lines.
    return front_matter.rstrip("\r\n") + nl + block


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = skipped_present = missing = 0
    for stem, (name, lat, lng, conf, _why) in sorted(COORDS.items()):
        path = os.path.join("_posts", stem + ".md")
        if not os.path.exists(path):
            print(f"  MISSING FILE  {stem}")
            missing += 1
            continue

        text = io.open(path, encoding="utf-8", newline="").read()
        fm, rest = split_front_matter(text)
        if fm is None:
            print(f"  NO FRONT MATTER  {stem}")
            missing += 1
            continue

        if has_coords(fm):
            skipped_present += 1
            continue

        new_text = "---" + ("\r\n" if "\r\n" in text[:80] else "\n") + apply_location(fm, name, lat, lng) + rest
        if not args.dry_run:
            io.open(path, "w", encoding="utf-8", newline="").write(new_text)
        print(f"  [{conf:6}] {stem}  ->  {name} ({lat}, {lng})")
        changed += 1

    verb = "would update" if args.dry_run else "updated"
    print(f"\n{verb}: {changed}   already had coords: {skipped_present}   problems: {missing}")


if __name__ == "__main__":
    sys.exit(main())

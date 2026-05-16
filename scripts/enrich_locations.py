"""
enrich_locations.py — one-shot script

Adds location: blocks to imported posts based on title-keyword matching,
updates trip files with corrected dates from user, and swaps each trip's
cover image to a more iconic post's first photo.

Safe to re-run: skips posts that already have a location: field.
"""
import os
import re
import glob

# CORRECTED TRIP DATES from user
TRIP_DATES = {
    "new-zealand":          ("2020-12-26", "2021-01-08"),
    "european-excursion":   ("2021-02-06", "2021-03-18"),
    "african-safari":       ("2024-08-23", "2024-09-14"),
    "bamboo-bulgogi":       ("2024-12-11", "2025-01-03"),
    "peruvian-passage":     ("2025-08-26", "2025-09-11"),
    "vietnam":              ("2025-12-08", "2026-01-04"),
}

# COVER POST per trip — iconic post whose first image becomes the trip cover
COVER_POSTS = {
    "new-zealand":          "hobbiton-pt1",
    "european-excursion":   "the-colosseum-interior",
    "european-exploration": "a-lake-como-hiking-day",
    "african-safari":       "a-full-day-in-kruger-national-park",
    "bamboo-bulgogi":       "mt-fuji-temples-shrines",
    "peruvian-passage":     "the-exploration-of-machu-picchu",
    "vietnam":              "ba-na-hills-the-golden-bridge",
}

# Title substring (lowercase) -> (display name, lat, lng). Most specific first.
LOCATIONS = [
    # Peru
    ("machu picchu",            ("Machu Picchu, Peru", -13.1631, -72.5450)),
    ("aguas calientes",         ("Aguas Calientes, Peru", -13.1538, -72.5252)),
    ("sacred valley",           ("Sacred Valley, Peru", -13.3447, -72.0700)),
    ("muyana",                  ("Muyana Lodge, Amazon", -3.7437, -73.2516)),
    ("piraha",                  ("Amazon Rainforest, Peru", -3.7437, -73.2516)),
    ("swimming in the amazon",  ("Amazon Rainforest, Peru", -3.7437, -73.2516)),
    ("amazon",                  ("Amazon Rainforest, Peru", -3.7437, -73.2516)),
    ("chocolate museum",        ("Cusco, Peru", -13.5170, -71.9785)),
    ("casa concha",             ("Cusco, Peru", -13.5170, -71.9785)),
    ("cusco",                   ("Cusco, Peru", -13.5170, -71.9785)),
    ("paracas",                 ("Paracas, Peru", -13.8350, -76.2486)),
    ("sandboard",               ("Paracas, Peru", -13.8350, -76.2486)),
    ("historic lima",           ("Lima, Peru", -12.0464, -77.0428)),
    ("adventure to peru",       ("Lima, Peru", -12.0464, -77.0428)),
    ("notes on peru",           ("Peru", -12.0464, -77.0428)),
    # Vietnam
    ("ha giang",                ("Ha Giang, Vietnam", 22.8233, 104.9844)),
    ("ga zang",                 ("Ha Giang, Vietnam", 22.8233, 104.9844)),
    ("ban gioc",                ("Ban Gioc Waterfall, Vietnam", 22.8530, 106.7233)),
    ("hanoi",                   ("Hanoi, Vietnam", 21.0285, 105.8542)),
    ("imperial city",           ("Imperial City, Hue", 16.4708, 107.5827)),
    ("ba na hills",             ("Ba Na Hills, Vietnam", 15.9988, 107.9988)),
    ("golden bridge",           ("Ba Na Hills, Vietnam", 15.9988, 107.9988)),
    ("marble mountains",        ("Marble Mountains, Da Nang", 16.0035, 108.2620)),
    ("hoi an",                  ("Hoi An, Vietnam", 15.8801, 108.3380)),
    ("birthday-the-beach",      ("Da Nang, Vietnam", 16.0544, 108.2022)),
    ("welcome to hue",          ("Hue, Vietnam", 16.4637, 107.5909)),
    ("our time in hue",         ("Hue, Vietnam", 16.4637, 107.5909)),
    ("flying to hanoi",         ("Hanoi, Vietnam", 21.0285, 105.8542)),
    ("hue",                     ("Hue, Vietnam", 16.4637, 107.5909)),
    ("hcmc",                    ("Ho Chi Minh City", 10.8231, 106.6297)),
    ("saigon",                  ("Ho Chi Minh City", 10.8231, 106.6297)),
    ("cu chi",                  ("Cu Chi Tunnels, Vietnam", 11.1421, 106.4636)),
    ("cao dai",                 ("Cao Dai Temple, Tay Ninh", 11.2922, 106.1364)),
    ("black virgin",            ("Black Virgin Mountain, Vietnam", 11.3791, 106.1721)),
    ("ben thanh",               ("Ho Chi Minh City", 10.7724, 106.6981)),
    ("bahn mi",                 ("Ho Chi Minh City", 10.8231, 106.6297)),
    ("war remnants",            ("War Remnants Museum, HCMC", 10.7791, 106.6924)),
    ("vietnamese tutor",        ("Ho Chi Minh City", 10.8231, 106.6297)),
    # Japan + Korea
    ("seoul",                   ("Seoul, South Korea", 37.5665, 126.9780)),
    ("gyeongbokgung",           ("Gyeongbokgung Palace, Seoul", 37.5796, 126.9770)),
    ("hanboks",                 ("Seoul, South Korea", 37.5665, 126.9780)),
    ("nanta theatre",           ("Seoul, South Korea", 37.5665, 126.9780)),
    ("dmz",                     ("DMZ, Korea", 37.9568, 126.6776)),
    ("south korea",             ("Seoul, South Korea", 37.5665, 126.9780)),
    ("itaewon",                 ("Itaewon, Seoul", 37.5345, 126.9938)),
    ("lotte world",             ("Lotte World Tower, Seoul", 37.5125, 127.1025)),
    ("war memorial of korea",   ("Seoul, South Korea", 37.5363, 126.9777)),
    ("national museum of korea",("Seoul, South Korea", 37.5240, 126.9803)),
    ("seoul book",              ("Seoul, South Korea", 37.5063, 127.0070)),
    ("hiroshima",               ("Hiroshima, Japan", 34.3853, 132.4553)),
    ("himeji",                  ("Himeji Castle, Japan", 34.8395, 134.6939)),
    ("kobe",                    ("Kobe, Japan", 34.6901, 135.1955)),
    ("nara",                    ("Nara Deer Park, Japan", 34.6851, 135.8048)),
    ("philosopher",             ("Kyoto, Japan", 35.0247, 135.7950)),
    ("tenryu-ji",               ("Arashiyama, Kyoto", 35.0094, 135.6717)),
    ("bamboo grove",            ("Arashiyama, Kyoto", 35.0094, 135.6717)),
    ("monkey park",             ("Arashiyama, Kyoto", 35.0094, 135.6772)),
    ("tori gates",              ("Fushimi Inari, Kyoto", 34.9671, 135.7727)),
    ("nij",                     ("Nijo Castle, Kyoto", 35.0142, 135.7480)),
    ("pontocho",                ("Pontocho, Kyoto", 35.0089, 135.7714)),
    ("kyoto",                   ("Kyoto, Japan", 35.0116, 135.7681)),
    ("lake kawaguchi",          ("Lake Kawaguchi, Japan", 35.5158, 138.7625)),
    ("mt fuji",                 ("Mt Fuji, Japan", 35.3606, 138.7274)),
    ("mt. fuji",                ("Mt Fuji, Japan", 35.3606, 138.7274)),
    ("sea candle",              ("Enoshima, Japan", 35.2960, 139.4818)),
    ("ramen street",            ("Tokyo, Japan", 35.6762, 139.6503)),
    ("tokyo tower",             ("Tokyo Tower", 35.6586, 139.7454)),
    ("imperial palace",         ("Imperial Palace, Tokyo", 35.6852, 139.7528)),
    ("hedgehog",                ("Tokyo, Japan", 35.6762, 139.6503)),
    ("loyal shiba",             ("Shibuya, Tokyo", 35.6580, 139.7016)),
    ("godzilla",                ("Shinjuku, Tokyo", 35.6938, 139.7036)),
    ("poop museum",             ("Yokohama, Japan", 35.4437, 139.6380)),
    ("oldest temple",           ("Senso-ji Temple, Tokyo", 35.7148, 139.7967)),
    ("sushi-making",            ("Tokyo, Japan", 35.6762, 139.6503)),
    ("cherry blossom",          ("Tokyo, Japan", 35.6762, 139.6503)),
    ("tokyo",                   ("Tokyo, Japan", 35.6762, 139.6503)),
    ("japan arrival",           ("Taipei, Taiwan", 25.0330, 121.5654)),
    ("taiwan",                  ("Taipei, Taiwan", 25.0330, 121.5654)),
    # Africa
    ("johannesburg",            ("Johannesburg, South Africa", -26.2041, 28.0473)),
    ("apartheid",               ("Apartheid Museum, Johannesburg", -26.2360, 28.0107)),
    ("military history",        ("Johannesburg, South Africa", -26.2041, 28.0473)),
    ("zambezi",                 ("Zambezi River, Zimbabwe", -17.9244, 25.8367)),
    ("zimbabwe",                ("Victoria Falls, Zimbabwe", -17.9243, 25.8572)),
    ("botswana",                ("Chobe National Park, Botswana", -17.8167, 25.0917)),
    ("kruger",                  ("Kruger National Park, South Africa", -23.9884, 31.5547)),
    ("overnight adventure",     ("Kruger National Park, South Africa", -23.9884, 31.5547)),
    ("botanical garden",        ("Cape Town, South Africa", -33.9249, 18.4241)),
    ("table mountain",          ("Table Mountain, Cape Town", -33.9628, 18.4098)),
    ("robben island",           ("Robben Island, Cape Town", -33.8067, 18.3661)),
    ("scuba south africa",      ("Cape Town, South Africa", -33.9249, 18.4241)),
    ("lion-s head",             ("Lions Head, Cape Town", -33.9389, 18.3895)),
    ("capetown",                ("Cape Town, South Africa", -33.9249, 18.4241)),
    ("cape town",               ("Cape Town, South Africa", -33.9249, 18.4241)),
    ("our last day in cape",    ("Cape Town, South Africa", -33.9249, 18.4241)),
    ("nine hours in paris",     ("Paris, France (layover)", 48.8566, 2.3522)),
    ("weekend in nyc",          ("New York City", 40.7128, -74.0060)),
    # European Excursion
    ("anne frank",              ("Anne Frank House, Amsterdam", 52.3752, 4.8840)),
    ("redlight",                ("Amsterdam, Netherlands", 52.3676, 4.9041)),
    ("cheese museum",           ("Amsterdam, Netherlands", 52.3676, 4.9041)),
    ("canal cheese",            ("Amsterdam, Netherlands", 52.3676, 4.9041)),
    ("jordaan",                 ("Amsterdam, Netherlands", 52.3676, 4.9041)),
    ("amsterdam",               ("Amsterdam, Netherlands", 52.3676, 4.9041)),
    ("checkpoint charlie",      ("Berlin, Germany", 52.5076, 13.3904)),
    ("ddr museum",              ("Berlin, Germany", 52.5193, 13.4019)),
    ("berlin",                  ("Berlin, Germany", 52.5200, 13.4050)),
    ("berliner",                ("Berlin, Germany", 52.5200, 13.4050)),
    ("imperial castle",         ("Nuremberg, Germany", 49.4521, 11.0767)),
    ("palace of justice",       ("Nuremberg, Germany", 49.4521, 11.0767)),
    ("nuremburg",               ("Nuremberg, Germany", 49.4521, 11.0767)),
    ("rhine",                   ("Sankt Goar, Germany", 50.1500, 7.7167)),
    ("sankt goar",              ("Sankt Goar, Germany", 50.1500, 7.7167)),
    ("dachau",                  ("Dachau Memorial, Germany", 48.2683, 11.4348)),
    ("hofbr",                   ("Munich, Germany", 48.1351, 11.5820)),
    ("english garden",          ("Munich, Germany", 48.1351, 11.5820)),
    ("f-ssen",                  ("Fussen, Germany", 47.5712, 10.7498)),
    ("munich",                  ("Munich, Germany", 48.1351, 11.5820)),
    ("vatican",                 ("Vatican City", 41.9029, 12.4534)),
    ("st peter",                ("St Peters Basilica, Vatican", 41.9022, 12.4574)),
    ("colosseum",               ("Colosseum, Rome", 41.8902, 12.4922)),
    ("roman forum",             ("Roman Forum, Rome", 41.8924, 12.4853)),
    ("roman baths",             ("Rome, Italy", 41.9028, 12.4964)),
    ("mouth of truth",          ("Rome, Italy", 41.8893, 12.4815)),
    ("note on rome",            ("Rome, Italy", 41.9028, 12.4964)),
    ("rome",                    ("Rome, Italy", 41.9028, 12.4964)),
    ("note on venice",          ("Venice, Italy", 45.4408, 12.3155)),
    ("views of venice",         ("Venice, Italy", 45.4408, 12.3155)),
    ("venice",                  ("Venice, Italy", 45.4408, 12.3155)),
    ("leaning tower",           ("Pisa, Italy", 43.7228, 10.4017)),
    ("pisa",                    ("Pisa, Italy", 43.7228, 10.4017)),
    ("accademia",               ("Florence, Italy", 43.7696, 11.2558)),
    ("palazzo vecchio",         ("Florence, Italy", 43.7696, 11.2558)),
    ("fontana del porcellino",  ("Florence, Italy", 43.7696, 11.2558)),
    ("florence",                ("Florence, Italy", 43.7696, 11.2558)),
    ("italian cooking",         ("Florence, Italy", 43.7696, 11.2558)),
    ("versailles",              ("Versailles, France", 48.8048, 2.1203)),
    ("sainte chappelle",        ("Sainte-Chappelle, Paris", 48.8554, 2.3450)),
    ("sainte-chappelle",        ("Sainte-Chappelle, Paris", 48.8554, 2.3450)),
    ("shakespeare company",     ("Shakespeare and Co., Paris", 48.8527, 2.3471)),
    ("louvre",                  ("Louvre, Paris", 48.8606, 2.3376)),
    ("pantheon",                ("Pantheon, Paris", 48.8462, 2.3464)),
    ("p-re-lachaise",           ("Pere Lachaise, Paris", 48.8614, 2.3939)),
    ("pere lachaise",           ("Pere Lachaise, Paris", 48.8614, 2.3939)),
    ("lock bridge",             ("Pont des Arts, Paris", 48.8587, 2.3373)),
    ("32nd birthday",           ("Paris, France", 48.8566, 2.3522)),
    ("birthday in paris",       ("Paris, France", 48.8566, 2.3522)),
    ("note on france",          ("Paris, France", 48.8566, 2.3522)),
    ("oh my god",               ("Paris, France", 48.8566, 2.3522)),
    ("paris",                   ("Paris, France", 48.8566, 2.3522)),
    ("manneken-pis",            ("Brussels, Belgium", 50.8458, 4.3499)),
    ("atomium",                 ("Brussels, Belgium", 50.8950, 4.3415)),
    ("waffles",                 ("Brussels, Belgium", 50.8503, 4.3517)),
    ("note on belgium",         ("Brussels, Belgium", 50.8503, 4.3517)),
    ("belgian chocolate",       ("Brussels, Belgium", 50.8503, 4.3517)),
    ("belgium architecture",    ("Brussels, Belgium", 50.8503, 4.3517)),
    ("torture museum",          ("Bruges, Belgium", 51.2093, 3.2247)),
    ("we love bruges",          ("Bruges, Belgium", 51.2093, 3.2247)),
    ("bruges",                  ("Bruges, Belgium", 51.2093, 3.2247)),
    ("croque-monsieur",         ("Bruges, Belgium", 51.2093, 3.2247)),
    ("stonehenge",              ("Stonehenge, UK", 51.1789, -1.8262)),
    ("british museum",          ("British Museum, London", 51.5194, -0.1270)),
    ("buckingham palace",       ("Buckingham Palace, London", 51.5014, -0.1419)),
    ("changing of the guard",   ("Buckingham Palace, London", 51.5014, -0.1419)),
    ("daunt bookstore",         ("London, UK", 51.5224, -0.1556)),
    ("sherlock holmes",         ("Baker Street, London", 51.5236, -0.1585)),
    ("chinatown",               ("London Chinatown", 51.5114, -0.1316)),
    ("fish chips",              ("London, UK", 51.5074, -0.1278)),
    ("welcome letter",          ("London, UK", 51.5074, -0.1278)),
    ("london",                  ("London, UK", 51.5074, -0.1278)),
    # European Exploration
    ("lake como",               ("Lake Como, Italy", 45.9594, 9.2895)),
    ("lierna",                  ("Lierna, Lake Como", 45.9594, 9.2895)),
    ("lecco",                   ("Lecco, Italy", 45.8556, 9.3978)),
    ("milan",                   ("Milan, Italy", 45.4642, 9.1900)),
    ("brindisi",                ("Brindisi, Italy", 40.6320, 17.9362)),
    ("ancient agora",           ("Ancient Agora, Athens", 37.9748, 23.7233)),
    ("acropolis",               ("Acropolis, Athens", 37.9715, 23.7257)),
    ("athens",                  ("Athens, Greece", 37.9838, 23.7275)),
    ("delos",                   ("Delos, Greece", 37.3938, 25.2715)),
    ("mykonos",                 ("Mykonos, Greece", 37.4467, 25.3289)),
    ("split",                   ("Split, Croatia", 43.5081, 16.4402)),
    ("heidelberg",              ("Heidelberg, Germany", 49.3988, 8.6724)),
    ("cologne",                 ("Cologne, Germany", 50.9375, 6.9603)),
    ("koblenz",                 ("Koblenz, Germany", 50.3569, 7.5890)),
    ("baden",                   ("Baden-Baden, Germany", 48.7611, 8.2397)),
    ("stuttgart",               ("Stuttgart, Germany", 48.7758, 9.1829)),
    ("dusseldorf",              ("Dusseldorf, Germany", 51.2277, 6.7735)),
    ("frankfurt",               ("Frankfurt, Germany", 50.1109, 8.6821)),
    ("mainz",                   ("Mainz, Germany", 49.9929, 8.2473)),
    ("bad homburg",             ("Bad Homburg, Germany", 50.2274, 8.6177)),
    ("switzerland",             ("Lugano, Switzerland", 46.0037, 8.9510)),
    # New Zealand
    ("hobbiton",                ("Hobbiton, New Zealand", -37.8721, 175.6831)),
    ("auckland zoo",            ("Auckland Zoo, NZ", -36.8629, 174.7196)),
    ("auckland",                ("Auckland, New Zealand", -36.8485, 174.7633)),
    ("dumplings",               ("Auckland, NZ", -36.8485, 174.7633)),
    ("glow worm",               ("Waitomo Caves, NZ", -38.2611, 175.1043)),
    ("rotorua",                 ("Rotorua, NZ", -38.1368, 176.2497)),
    ("redwood",                 ("Rotorua Redwoods, NZ", -38.1368, 176.2497)),
    ("huka falls",              ("Huka Falls, NZ", -38.6406, 176.0884)),
    ("mt doom",                 ("Tongariro National Park, NZ", -39.1576, 175.6362)),
    ("gisborne",                ("Gisborne, NZ", -38.6624, 178.0177)),
    ("queenstown",              ("Queenstown, NZ", -45.0312, 168.6626)),
    ("bungee",                  ("Queenstown, NZ", -45.0312, 168.6626)),
    ("w-naka",                  ("Wanaka, NZ", -44.6986, 169.1486)),
    ("wanaka",                  ("Wanaka, NZ", -44.6986, 169.1486)),
    ("milford",                 ("Milford Sound, NZ", -44.6712, 167.9192)),
    ("doubtful",                ("Doubtful Sound, NZ", -45.4506, 167.0394)),
    ("mt cook",                 ("Mt Cook (Aoraki), NZ", -43.5985, 170.1421)),
    ("blue pools",              ("Blue Pools, Haast, NZ", -44.0813, 169.0432)),
    ("franz",                   ("Franz Josef Glacier, NZ", -43.3776, 170.1819)),
    ("glaciers",                ("Franz Josef Glacier, NZ", -43.3776, 170.1819)),
    ("hokitika",                ("Hokitika, NZ", -42.7176, 170.9683)),
    ("jade",                    ("Hokitika, NZ", -42.7176, 170.9683)),
    ("south island",            ("South Island, NZ", -45.0312, 168.6626)),
]


def find_first_image(content):
    parts = content.split('---', 2)
    body = parts[2] if len(parts) >= 3 else content
    m = re.search(r'!\[[^\]]*\]\(([^)\s]+)', body)
    return m.group(1) if m else None


def add_location_to_post(path):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    parts = content.split('---', 2)
    if len(parts) < 3:
        return None
    front = parts[1]
    if 'location:' in front:
        return None
    tm = re.search(r'title:\s*"([^"]+)"', front)
    if not tm:
        return None
    title_lower = tm.group(1).lower()
    fname_lower = os.path.basename(path).lower()
    matched = None
    for key, value in LOCATIONS:
        if key in title_lower or key in fname_lower:
            matched = value
            break
    if not matched:
        return None
    name, lat, lng = matched
    loc = 'location:\n  name: "' + name + '"\n  lat: ' + str(lat) + '\n  lng: ' + str(lng) + '\n'
    new_front = front.rstrip() + '\n' + loc
    new_content = '---' + new_front + '---' + parts[2]
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return name


def main():
    loc_count = 0
    no_match = []
    for path in sorted(glob.glob('_posts/*.md')):
        result = add_location_to_post(path)
        if result:
            loc_count += 1
        else:
            with open(path, encoding='utf-8') as f:
                c = f.read()
            if 'location:' not in c[:1500]:
                no_match.append(os.path.basename(path))

    print('Added location to ' + str(loc_count) + ' posts.')
    print('No match for ' + str(len(no_match)) + ' posts:')
    for name in no_match[:20]:
        print('  - ' + name)
    if len(no_match) > 20:
        print('  ... and ' + str(len(no_match) - 20) + ' more')

    print()
    for slug, (start, end) in TRIP_DATES.items():
        trip_path = '_trips/' + slug + '.md'
        if not os.path.exists(trip_path):
            continue
        with open(trip_path, encoding='utf-8') as f:
            c = f.read()
        c = re.sub(r'start_date:\s*\d{4}-\d{2}-\d{2}', 'start_date: ' + start, c)
        c = re.sub(r'end_date:\s*\d{4}-\d{2}-\d{2}', 'end_date: ' + end, c)
        cover_key = COVER_POSTS.get(slug)
        if cover_key:
            matches = [p for p in glob.glob('_posts/*.md') if cover_key in os.path.basename(p)]
            if matches:
                with open(matches[0], encoding='utf-8') as f:
                    pc = f.read()
                img = find_first_image(pc)
                if img:
                    c = re.sub(r'cover:\s*\S+', 'cover: ' + img, c, count=1)
                    print('  ' + slug + ': cover from ' + os.path.basename(matches[0]))
        with open(trip_path, 'w', encoding='utf-8') as f:
            f.write(c)


if __name__ == '__main__':
    main()

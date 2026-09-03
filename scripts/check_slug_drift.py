#!/usr/bin/env python3
"""
check_slug_drift.py — posts whose URL no longer matches their title
=============================================================================
WHY THIS EXISTS
    The editor names a post's file when the post is created, from whatever
    the title was at that moment, and never renames it again. Retitle the
    post and the old words stay in the URL for good.

    That is how a post titled "If the Earth were a single state, Istanbul
    would be its capital" ended up living at /blue-skies-seaside-black-tea/
    while a completely different post carried that title — and how another
    one was published at the address /draft/, because it was created before
    it had a name.

    Nothing about the site breaks when this happens, which is exactly why it
    goes unnoticed until someone reads a URL out loud.

HOW IT JUDGES
    Not on an exact match — plenty of good slugs are a deliberate shortening
    of a long title, and flagging those would make this noise. It asks how
    much of the title still survives in the slug, ignoring small words, and
    reports anything under half.

    Accents are folded before comparing, so "Bánh Cuốn & Ha Long Bay" at
    /banh-cuon-ha-long-bay/ counts as the match it obviously is.

FIXING ONE
    Renaming is safe, but it is a URL change, so:
      1. Check the post has no comments. The Cusdis thread is keyed on the
         old path and does not follow a rename:
             curl -sG https://cusdis.com/api/open/comments \\
               --data-urlencode "appId=<site.cusdis_app_id>" \\
               --data-urlencode "pageId=/<category>/<old-slug>"
      2. git mv the file, keeping its date prefix.
      3. Add a [[redirects]] pair in netlify.toml so the old address keeps
         working. There are worked examples in there already.

USAGE
    python scripts/check_slug_drift.py

Exit codes: 0 = ran (whether or not it found anything), 1 = could not run.
"""

import glob
import os
import re
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

try:
    import yaml
except ImportError:
    print("pyyaml is not installed — pip install pyyaml")
    sys.exit(1)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Words too common to say anything about whether a slug matches its title.
SMALL = set("a an the and or of to in on at for from with by is was were be "
            "its it i we our my me you your this that as but if so".split())

THRESHOLD = 0.5


def fold(text):
    """Lowercase, strip accents and punctuation: 'Bánh Cuốn!' -> 'banh-cuon'."""
    text = text.lower().replace("'", "").replace("’", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def significant(text):
    return [w for w in fold(text).split("-") if w and w not in SMALL]


def main():
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "_posts", "*.md"))):
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
        found = re.match(r"\A---\s*\n(.*?\n)---\s*\n", raw, re.S)
        if not found:
            continue
        try:
            front = yaml.safe_load(found.group(1)) or {}
        except yaml.YAMLError:
            continue
        title = str(front.get("title") or "").strip()
        if not title:
            continue

        slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", os.path.basename(path)[:-3])
        title_words = significant(title)
        if not title_words:
            continue
        slug_words = set(significant(slug))
        shared = sum(1 for w in title_words if w in slug_words)
        rows.append((shared / float(len(title_words)), slug, title,
                     front.get("categories")))

    rows.sort()
    drifted = [r for r in rows if r[0] < THRESHOLD]

    if not drifted:
        print("Every post's URL still reflects its title. (%d checked)" % len(rows))
        return 0

    print("Posts whose URL no longer matches their title (worst first):\n")
    for overlap, slug, title, categories in drifted:
        category = categories[0] if isinstance(categories, list) and categories \
            else (categories or "?")
        print("  %d%% of the title survives in the slug" % round(overlap * 100))
        print("       url:   /%s/%s/" % (category, slug))
        print("       title: %s" % " ".join(title.split()))
        print()
    print("%d of %d posts. See the header of this file before renaming one."
          % (len(drifted), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
publish_ready.py — publish everything in Ready, in one deploy
=============================================================================
WHY THIS EXISTS
    Netlify bills a build per PUSH, not per commit. Merging seven posts one at
    a time in the GitHub UI is seven pushes to main and therefore seven builds
    — and GitHub has no "merge all" button anyway.

    This merges every Ready branch locally and pushes once. Seven posts, one
    build. The commits stay separate, one per post, so the history still says
    who wrote what and when; that costs nothing, because the build count
    follows the push.

WHAT "READY" MEANS
    Decap's editorial workflow keeps a post's status in the pull request's
    label, not in the branch name:

        decap-cms/draft            still being written
        decap-cms/pending_review   waiting to be looked at
        decap-cms/pending_publish  Ready  <- only these are merged

    That is why this asks GitHub rather than just merging every cms/ branch.
    A branch-only script would publish half-written drafts, and the branch
    gives no clue which is which.

WHAT IT DOES
    1. Asks GitHub which open PRs are labelled Ready.
    2. Fetches, and merges each of those branches into local main.
    3. Re-runs the generators, since a tag edit or a new trip changes the
       lists baked into admin/config.yml.
    4. Checks every post still parses before anything leaves the machine.
    5. Pushes once.

    GitHub closes the pull requests by itself when their commits land in main,
    and the branch-cleanup workflow removes the branches.

SAFETY
    - Prints the plan and does nothing unless you pass --push.
    - Refuses to run with uncommitted changes, so your work is never swept
      into someone else's merge.
    - Skips a branch that conflicts rather than leaving a half-merged tree,
      and says which one needs hands.
    - If a check fails after merging, it stops WITHOUT pushing and leaves the
      merges in place for you to look at. `git reset --hard origin/main` puts
      everything back.

USAGE
    python scripts/publish_ready.py            # what would be published
    python scripts/publish_ready.py --push     # publish it, one build

Exit codes: 0 = done (or nothing to publish), 1 = stopped, nothing pushed.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "rojamich/travels"
READY_LABEL = "decap-cms/pending_publish"
GENERATORS = ("sort_tags.py", "sync_tag_options.py",
              "sync_trip_filters.py", "sync_country_options.py")


def git(*args, check=True):
    result = subprocess.run(("git",) + args, cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result


def ready_pull_requests():
    """Open PRs labelled Ready, newest first. Read-only, so no token needed."""
    url = ("https://api.github.com/repos/%s/pulls?state=open&per_page=100" % REPO)
    request = urllib.request.Request(url, headers={
        "User-Agent": "travel-blog publish-ready",
        "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    if not isinstance(payload, list):
        raise RuntimeError("GitHub said: %s" % payload.get("message", payload))

    ready = []
    for pull in payload:
        labels = [label["name"] for label in pull.get("labels", [])]
        if READY_LABEL in labels:
            ready.append({"number": pull["number"], "branch": pull["head"]["ref"],
                          "title": pull["title"]})
    return ready


def already_merged(branch):
    """True if the branch tip is already an ancestor of main."""
    return git("merge-base", "--is-ancestor", "origin/" + branch, "HEAD",
               check=False).returncode == 0


def run_generators():
    """The lists baked into admin/config.yml, rebuilt from the merged content."""
    changed = False
    for name in GENERATORS:
        path = os.path.join(ROOT, "scripts", name)
        if not os.path.exists(path):
            continue
        result = subprocess.run((sys.executable, path), cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        first_line = (result.stdout or result.stderr or "").strip().split("\n")[0]
        print("    %-26s %s" % (name, first_line[:74]))
        if result.returncode != 0:
            raise RuntimeError("%s failed" % name)
    if git("status", "--porcelain").stdout.strip():
        changed = True
    return changed


def posts_parse():
    """Every post and trip still has readable front matter."""
    try:
        import yaml
    except ImportError:
        print("    pyyaml not installed — skipping the front matter check")
        return True

    import glob
    pattern = re.compile(r"\A---\s*\n(.*?\n)---\s*\n", re.S)
    bad = []
    for path in glob.glob(os.path.join(ROOT, "_posts", "*.md")) + \
            glob.glob(os.path.join(ROOT, "_trips", "*.md")):
        with open(path, encoding="utf-8") as handle:
            found = pattern.match(handle.read())
        if not found:
            bad.append(os.path.basename(path))
            continue
        try:
            yaml.safe_load(found.group(1))
        except yaml.YAMLError:
            bad.append(os.path.basename(path))
    if bad:
        print("    front matter will not parse in: %s" % ", ".join(bad[:5]))
        return False
    print("    every post and trip parses")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Merge everything in Ready and push once, for one build.")
    parser.add_argument("--push", action="store_true",
                        help="actually merge and push. Without it, prints the plan.")
    args = parser.parse_args()

    if git("status", "--porcelain").stdout.strip():
        print("You have uncommitted changes. Commit or stash them first — this\n"
              "script pushes main, and anything sitting in the tree would go with it.")
        return 1

    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != "main":
        print("On branch %s, not main. Switch to main first." % branch)
        return 1

    print("asking GitHub what is Ready...")
    try:
        ready = ready_pull_requests()
    except Exception as exc:                          # noqa: BLE001
        print("Could not reach GitHub: %s" % exc)
        return 1

    git("fetch", "origin", "--prune")

    # Bring local main up to date first. Fast-forward only: if main has
    # wandered off on its own — a local commit here, her CMS commits there —
    # that wants a person looking at it, not a script quietly merging around
    # it on the way to a push.
    if git("merge", "--ff-only", "origin/main", check=False).returncode != 0:
        behind = git("rev-list", "--count", "HEAD..origin/main").stdout.strip()
        ahead = git("rev-list", "--count", "origin/main..HEAD").stdout.strip()
        print("Local main and origin/main have diverged — %s commit(s) here" 
              " that aren't there, and %s there that aren't here.\n"
              "Sort that out first, then re-run:\n"
              "    git pull\n\n"
              "Nothing was merged and nothing was pushed." % (ahead, behind))
        return 1

    pending = [pull for pull in ready if not already_merged(pull["branch"])]
    settled = len(ready) - len(pending)

    print("\n%d pull request(s) marked Ready." % len(ready))
    if settled:
        print("%d already in main (GitHub just hasn't closed them)." % settled)
    if not pending:
        print("Nothing to publish.")
        return 0

    print("\nwould publish:" if not args.push else "\npublishing:")
    for pull in pending:
        print("  #%-4s %s" % (pull["number"], pull["title"][:70]))

    if not args.push:
        print("\nNothing merged and nothing pushed. Re-run with --push to publish\n"
              "all %d in a single build." % len(pending))
        return 0

    print()
    merged, skipped = [], []
    for pull in pending:
        reference = "origin/" + pull["branch"]
        result = git("merge", "--no-ff", reference,
                     "-m", "Merge %s" % pull["branch"], check=False)
        if result.returncode == 0:
            merged.append(pull)
            print("  merged   #%s" % pull["number"])
        else:
            git("merge", "--abort", check=False)
            skipped.append(pull)
            print("  CONFLICT #%s %s — skipped, needs hands" % (pull["number"],
                                                               pull["branch"]))

    if not merged:
        print("\nNothing merged cleanly. Nothing pushed.")
        return 1

    print("\n  regenerating the editor's lists:")
    try:
        if run_generators():
            git("add", "-A")
            git("commit", "-m", "Editor: refresh the generated lists after the merges")
            print("    committed the refreshed lists")
    except RuntimeError as exc:
        print("    %s\nStopped before pushing. The merges are still here; "
              "`git reset --hard origin/main` undoes them." % exc)
        return 1

    print("\n  checking before it leaves the machine:")
    if not posts_parse():
        print("\nStopped before pushing. The merges are still here; "
              "`git reset --hard origin/main` undoes them.")
        return 1

    print("\npushing once...")
    try:
        git("push", "origin", "main")
    except RuntimeError as exc:
        print("Push failed: %s\nSomeone may have pushed while this ran. "
              "Re-run and it will pick up from there." % exc)
        return 1

    print("\nPublished %d post(s) in one build." % len(merged))
    if skipped:
        print("%d needed hands and were left alone:" % len(skipped))
        for pull in skipped:
            print("    #%s %s" % (pull["number"], pull["branch"]))
    print("GitHub will close the pull requests as it notices the commits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

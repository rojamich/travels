#!/usr/bin/env python3
"""
preview_gate.py — build a post's preview only once it is up for review
=============================================================================
Netlify runs this before every build, as the `ignore` command in
netlify.toml. Exit 0 means "skip this build"; exit 1 means "build it".

WHY THIS EXISTS
    Editorial workflow opens a pull request for every post, and Netlify
    builds a deploy preview for every push to it. So every Save built the
    whole site again, and on a day of writing several posts the deploy list
    filled with previews of half-finished drafts. Finding the one preview
    worth looking at meant scrolling past dozens of them.

    Previews cost nothing in credits; this is about keeping the list
    readable, not about money.

THE RULE
    A post's status lives in its pull request's label (see publish_ready.py):

        decap-cms/draft            Drafts      -> skip, no preview
        decap-cms/pending_review   In Review   -> build the preview
        decap-cms/pending_publish  Ready       -> build the preview

    A post branch with no status label yet is treated as a draft: that is
    the moment just after the first Save, before Decap has labelled it.

    Moving a card to In Review changes a label and pushes nothing, so on its
    own it would never start a build. .github/workflows/preview-on-review.yml
    supplies the push.

WHAT IT NEVER TOUCHES
    Production builds, and previews of anything that is not a post branch
    (cms/...) — code changes keep their previews exactly as before.

WHEN IN DOUBT, BUILD
    If GitHub cannot be asked (network, rate limit, anything at all), the
    build goes ahead. A preview nobody needed is a line in a list; a missing
    preview is her not being able to check her post.

    The lookup is a public, unauthenticated read. If GitHub's anonymous rate
    limit ever bites, set PREVIEW_GATE_TOKEN in Netlify's environment
    variables to any GitHub token and it is used instead.

Try it by hand, as Netlify would for pull request 605:

    CONTEXT=deploy-preview HEAD=cms/posts/x REVIEW_ID=605 python scripts/preview_gate.py
"""

import json
import os
import sys
import urllib.request

REPO = "rojamich/travels"
REVIEW_LABELS = ("decap-cms/pending_review", "decap-cms/pending_publish")

SKIP, BUILD = 0, 1


def labels_of(pull_number):
    url = "https://api.github.com/repos/%s/issues/%s/labels" % (REPO, pull_number)
    headers = {"User-Agent": "travel-blog preview-gate",
               "Accept": "application/vnd.github+json"}
    token = os.environ.get("PREVIEW_GATE_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return [label["name"] for label in json.load(response)]


def decide(env):
    """(exit code, reason) for the build Netlify is about to run."""
    if env.get("CONTEXT") != "deploy-preview":
        return BUILD, "not a deploy preview (%s)" % env.get("CONTEXT", "unknown")

    branch = env.get("HEAD", "")
    if not branch.startswith("cms/"):
        return BUILD, "not a post branch (%s)" % branch

    pull_number = env.get("REVIEW_ID", "")
    if not pull_number.isdigit():
        return BUILD, "no pull request number to look up"

    try:
        labels = labels_of(pull_number)
    except Exception as exc:                          # noqa: BLE001
        return BUILD, "could not ask GitHub (%s), building to be safe" % exc

    status = [l for l in labels if l.startswith("decap-cms/")]
    if any(l in REVIEW_LABELS for l in status):
        return BUILD, "#%s is %s" % (pull_number, ", ".join(status))
    return SKIP, "#%s is %s, so no preview until it moves to In Review" % (
        pull_number, ", ".join(status) or "unlabelled (a first save)")


def main():
    code, reason = decide(os.environ)
    print("preview gate: %s — %s" % ("building" if code == BUILD else "skipping", reason))
    return code


if __name__ == "__main__":
    sys.exit(main())

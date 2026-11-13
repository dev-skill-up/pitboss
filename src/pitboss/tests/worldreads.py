"""What the gate reads once for a world's project (keyword: gate)."""

import re
from typing import Mapping

# the listing of every open ticket of a repository (keyword: unlabeled)
UNLABELED_LISTING = re.compile(r"^repos/[\w.-]+/[\w.-]+/issues\?state=open&per_page")
SEARCH = re.compile(r"^search/issues\?q=")
# what mentions a ticket: a world that cans none has no mention
TIMELINE = re.compile(r"^repos/[\w.-]+/[\w.-]+/issues/\d+/timeline")
OPEN_LISTING = re.compile(r"^(repos/[^/]+/[^/]+)/pulls\?state=open")

# the login, and each repository's sizes of merged PRs (none)
GATE_READS: Mapping[str, object] = {
    "user": {"login": "pitboss-bot"},
    **{
        f"name={name}": {"data": {"repository": {"pullRequests": {"nodes": []}}}}
        for name in ("project", "lib", "pitboss")
    },
}


def listed_whole(bodies: Mapping[str, object], path: str, body: object) -> object:
    """A listing of open pull requests whose rows are the pulls the world holds.

    GitHub's listing row carries the pull's title, body, branch and draft flag; a
    world that lists only numbers gets each row filled from its pull.

    Args:
        bodies: the world's bodies.
        path: the path asked for.
        body: what the world cans for it.

    Returns:
        The body, each row of an open-pulls listing filled from its pull.
    """
    found = OPEN_LISTING.match(path)
    if not found or not isinstance(body, list):
        return body
    return [_filled(bodies, found[1], row) for row in body]


def _filled(bodies: Mapping[str, object], repo: str, row: object) -> object:
    pull = (
        bodies.get(f"{repo}/pulls/{row.get('number')}")
        if isinstance(row, dict)
        else None
    )
    return {**pull, **row} if isinstance(pull, dict) and isinstance(row, dict) else row


def none_listed(path: str) -> object:
    """What a world that cans no such list or search answers.

    Args:
        path: the ``gh api`` path.

    Returns:
        An empty list (a listing of every open ticket, a timeline) or search;
        None for any other path.
    """
    if UNLABELED_LISTING.match(path) or TIMELINE.match(path):
        return []
    return {"items": []} if SEARCH.match(path) else None

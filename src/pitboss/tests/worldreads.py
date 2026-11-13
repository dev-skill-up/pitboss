"""What the gate reads once for a world's project (keyword: gate)."""

import re
import urllib.parse
from typing import Iterator, Mapping, Sequence

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


# an organisation's search, oldest first (keyword: org-search)
ORG_SEARCH = re.compile(
    r"^search/issues\?q=org%?3?A?:?([^+&]+)\+is(?::|%3A)open\+([^&]*)"
    r"&sort=created&order=asc&per_page=100&page=(\d+)$"
)
API = "https://api.github.com/"


def org_searched(bodies: Mapping[str, object], path: str) -> object:
    """What GitHub's search of an organisation answers, from the world's listings.

    A world cans each repository's open pull requests and each label's open
    tickets; the search answers those of the organisation's repositories, oldest
    first, a page of 100 at a time.

    Args:
        bodies: the world's bodies.
        path: the path asked for.

    Returns:
        The search's answer; None when the path is no organisation's search.
    """
    found = ORG_SEARCH.match(path)
    if not found:
        return None
    terms = urllib.parse.unquote(found[2]).split("+")
    every = sorted(_items(bodies, found[1], terms), key=lambda each: each[0])
    number = int(found[3])
    items = [item for _, item in every][(number - 1) * 100 : number * 100]
    return {"total_count": len(every), "items": items}


def _items(
    bodies: Mapping[str, object], org: str, terms: Sequence[str]
) -> Iterator[tuple[str, Mapping[str, object]]]:
    # each canned item the search finds, with its age
    pulls = "is:pr" in terms
    labels = [each.removeprefix("label:") for each in terms if each.startswith("label:")]
    for key, body in bodies.items():
        repo = _listed_repo(key, org, pulls, labels)
        if repo and isinstance(body, list):
            for row in listed_whole(bodies, key, body):
                if isinstance(row, dict) and _wanted(row, pulls, terms):
                    item = {**row, "repository_url": f"{API}repos/{repo}"}
                    yield str(row.get("created_at", "")), item


def _listed_repo(key: str, org: str, pulls: bool, labels: Sequence[str]) -> str:
    # the repository of a canned listing the search reads, empty for another
    shape = (
        r"/pulls\?state=open"
        if pulls
        else r"/issues\?state=open&labels=(?:" + "|".join(map(re.escape, labels)) + ")"
    )
    found = re.match(
        rf"^repos/({re.escape(org)}/[\w.-]+){shape}(?:&sort=created&direction=asc)?"
        r"(?:&per_page=100&page=\d+)?$",
        key,
    )
    return found[1] if found and (pulls or labels) else ""


def _wanted(row: Mapping[str, object], pulls: bool, terms: Sequence[str]) -> bool:
    # a pull request whose branch the head qualifier takes; a ticket that is one
    if not pulls:
        return "pull_request" not in row
    head = row.get("head")
    branch = str(head.get("ref", "")) if isinstance(head, dict) else ""
    for each in terms:
        if each.startswith("head:") and not branch.startswith(each[5:]):
            return False
        if each.startswith("-head:") and branch.startswith(each[6:]):
            return False
    return True

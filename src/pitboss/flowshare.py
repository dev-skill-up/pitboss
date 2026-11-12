"""The share of pitboss PRs that changed the flow in the last 7 days (flow-share).

Owner, pitboss#444 item 13: the flow is changed by PR after PR, and the number says
how often. ``read`` lists the PRs merged in the window and their files;
``line`` is what ``pitboss count`` prints. Nothing is cached.
"""

import datetime
import json
from typing import Sequence

from . import flowfiles, ghapi, pullfiles

DAYS = 7
PITBOSS = "pitboss"


def _merged(text: str) -> Sequence[tuple[int, str]]:
    return [
        (int(each["number"]), str(each["merged_at"]))
        for each in json.loads(text)
        if each.get("merged_at")
    ]


def read(
    github: ghapi.GitHub, slug: str, now: datetime.datetime
) -> Sequence[Sequence[str]]:
    """The files of each PR merged in the last 7 days.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        now: the time now.

    Returns:
        The paths each PR changed, a list for each PR.
    """
    since = now - datetime.timedelta(days=DAYS)
    closed = ghapi.pages(
        github,
        f"repos/{slug}/pulls?state=closed&sort=updated&direction=desc",
        _merged,
        limit=3,
    )
    return [
        ghapi.pages(github, f"repos/{slug}/pulls/{number}/files", pullfiles.file_names)
        for number, merged in closed
        if datetime.datetime.fromisoformat(merged) >= since
    ]


def line(slug: str, pulls: Sequence[Sequence[str]]) -> str:
    """The line ``count`` prints.

    Args:
        slug: the repository's ``owner/name``.
        pulls: the paths each PR merged in the last 7 days changed.

    Returns:
        How many of the PRs changed a module of the flow and their share, or
        that none was merged.
    """
    changed = sum(bool(flowfiles.modules_of(each)) for each in pulls)
    if not pulls:
        return f"flow: no PR of {slug} was merged in the last {DAYS} days"
    return (
        f"flow: {changed} of {len(pulls)} PRs of {slug} merged in the last {DAYS}"
        f" days changed the flow ({100 * changed // len(pulls)}%)"
    )

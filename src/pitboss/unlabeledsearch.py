"""The tickets with no priority label, found by one search (keyword: unlabeled-search).

``unlabeled`` lists every open issue of every repository to find the few with no
priority label, so its pages grow with the queue. The search asks for the issues
that lack the first priority labels, so the pages read are the unlabeled tickets
and a few others, whatever the number of tickets with a label (pitboss#443).
"""

import json
from typing import Sequence

from . import config, ghapi, unlabeled

SEARCH_NOT = 4  # GitHub's search takes at most five operators
Found = tuple[str, str, frozenset[str]]


def _found(text: str) -> Sequence[Found]:
    # a page of the search, one entry for each raw item
    return [
        (
            each["created_at"],
            each["repository_url"].rsplit("/repos/", 1)[-1] + f"#{each['number']}",
            frozenset(name["name"] for name in each["labels"]),
        )
        for each in json.loads(text)["items"]
    ]


def _query(settings: config.Config) -> str:
    owners = sorted({each.owner for each in config.repositories(settings)})
    known = settings.slots.priority_labels[:SEARCH_NOT]
    words = [
        *(f"user:{each}" for each in owners),
        "is:issue",
        "is:open",
        *(f"-label:{each}" for each in known),
    ]
    return f"search/issues?q={'+'.join(words)}"


def references(github: ghapi.GitHub, settings: config.Config) -> Sequence[str]:
    """The open tickets with no priority label, oldest first.

    Args:
        github: the API.
        settings: the configuration; with no priority labels configured nothing
            is unlabeled.

    Returns:
        Each ticket as ``owner/name#number`` of a configured repository, oldest
        first by creation time.
    """
    known = settings.slots.priority_labels
    if not known:
        return []
    found = [
        (created, reference)
        for created, reference, names in ghapi.pages(github, _query(settings), _found)
        if config.has(settings, reference)
        and not any(each in known or unlabeled.PRIORITY.match(each) for each in names)
    ]
    return [reference for _, reference in sorted(found)]


def lines(github: ghapi.GitHub, settings: config.Config) -> Sequence[str]:
    """The ``NO PRIORITY LABEL`` lines and, after them, the rule.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        A line for each unlabeled ticket then the rule's line; none when every
        ticket has a priority label.
    """
    found = references(github, settings)
    if not found:
        return []
    return [*(f"{unlabeled.NO_LABEL} {each}" for each in found), unlabeled.RULE]

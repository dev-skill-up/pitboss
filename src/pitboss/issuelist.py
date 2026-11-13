"""The issues list holds PRs: its pages are counted by raw items (pitboss#391)."""

import json
from typing import Mapping, Sequence

from . import shapes
from .totaljson import text


def issue_of(item: Mapping[str, object]) -> shapes.Issue | None:
    """The issue an item of a list or a search is.

    Args:
        item: the raw item.

    Returns:
        The issue; none for a pull request, which the lists include.
    """
    if "pull_request" in item:
        return None
    labels = item.get("labels")
    named = (
        [each for each in labels if isinstance(each, dict)]
        if isinstance(labels, list)
        else []
    )
    return shapes.Issue(
        number=int(str(item["number"])),
        title=text(item.get("title")),
        created_at=text(item.get("created_at")),
        labels=frozenset(text(each.get("name")) for each in named),
        body=text(item.get("body")),
        comments=int(str(item.get("comments") or 0)),
    )


def listed(body: str) -> Sequence[shapes.Issue | None]:
    """Parse a page of the issues list, one entry for each raw item.

    Args:
        body: the response body of ``issues``.

    Returns:
        The issue of each item, or none for a PR (which the list includes), so
        that the length is the page's own.
    """
    return [issue_of(item) for item in json.loads(body)]


def issues(body: str) -> Sequence[shapes.Issue]:
    """Parse a page of issues, leaving out PRs (which the list includes).

    Args:
        body: the response body of ``issues``.

    Returns:
        The issues.
    """
    return list(filter(None, listed(body)))

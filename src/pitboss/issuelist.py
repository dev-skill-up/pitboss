"""The issues list holds PRs: its pages are counted by raw items (pitboss#391)."""

import json
from typing import Sequence, TypedDict

from . import shapes


class _Label(TypedDict):
    name: str


class _Raw(TypedDict, total=False):
    # an item of the issues list, as GitHub sends it
    number: int
    title: str
    created_at: str
    labels: list[_Label]
    body: str | None
    comments: int | None
    pull_request: object


def _issue(item: _Raw) -> shapes.Issue | None:
    if "pull_request" in item:
        return None
    return shapes.Issue(
        number=item["number"],
        title=item["title"],
        created_at=item["created_at"],
        labels=frozenset(label["name"] for label in item["labels"]),
        body=item.get("body") or "",
        comments=item.get("comments") or 0,
    )


def listed(text: str) -> Sequence[shapes.Issue | None]:
    """Parse a page of the issues list, one entry for each raw item.

    Args:
        text: the response body of ``issues``.

    Returns:
        The issue of each item, or none for a PR (which the list includes), so
        that the length is the page's own.
    """
    return [_issue(item) for item in json.loads(text)]


def issues(text: str) -> Sequence[shapes.Issue]:
    """Parse a page of issues, leaving out PRs (which the list includes).

    Args:
        text: the response body of ``issues``.

    Returns:
        The issues.
    """
    return list(filter(None, listed(text)))


def issue_of(text: str) -> Sequence[shapes.Issue]:
    """Parse one issue (the response body of ``issues/<number>``).

    Args:
        text: the response body.

    Returns:
        The issue, or none when it is a PR (which the issues include).
    """
    return issues(f"[{text}]")

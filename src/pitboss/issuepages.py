"""A page of issues, parsed (keyword: issue-page, pitboss#94)."""

import json
from typing import Any, Sequence

from . import shapes


def _issue(item: dict[str, Any]) -> shapes.Issue:
    return shapes.Issue(
        number=item["number"],
        title=item["title"],
        created_at=item["created_at"],
        labels=frozenset(label["name"] for label in item["labels"]),
        body=item.get("body") or "",
        comments=item.get("comments") or 0,
    )


def entries(text: str) -> Sequence[shapes.Issue | None]:
    """Parse a page of issues: the issue of each item, None for a PR.

    A page of 100 items is full whether or not some are PRs (pitboss#94).

    Args:
        text: the response body of ``issues``.

    Returns:
        An entry for each raw item.
    """
    return [
        None if "pull_request" in each else _issue(each) for each in json.loads(text)
    ]

"""The tickets a PR fixes: by a ``Fixes`` line in its title or body, or by its branch.

A mention in a Plan or an Evidence block names no ticket the PR works on
(keyword: taken, pitboss#448).
"""

import re
from typing import AbstractSet

from . import config, slotbook

_TRAILING_NUMBER = re.compile(r"[-/](\d+)$")
_ISSUE_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")
_CLOSING = re.compile(r"\b(?:Fixes|Closes)\s+(\S+)", re.IGNORECASE)
_NAME = re.compile(r"(?:[\w.-]+/)?[\w.-]*#\d+")


def names(title: str, body: str, branch: str, repo: config.Repo) -> AbstractSet[str]:
    """The tickets a PR fixes in its title or body, or names by its branch.

    Args:
        title: the PR's title.
        body: the PR's body.
        branch: the PR's head branch.
        repo: the PR's repository, which owns a bare ``#N``.

    Returns:
        The tickets' references.
    """
    found: set[str] = set()
    for closing in _CLOSING.finditer(f"{title}\n{body}"):
        named = _NAME.match(closing.group(1))
        url = _ISSUE_URL.search(closing.group(1))
        if named:
            found.add(slotbook.reference(named.group(0), repo))
        elif url:
            found.add(f"{url.group(1)}#{url.group(2)}")
    trailing = _TRAILING_NUMBER.search(branch)
    if trailing:
        found.add(f"{repo.slug}#{trailing.group(1)}")
    return frozenset(found)

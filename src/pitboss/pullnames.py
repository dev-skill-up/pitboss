"""The tickets a PR names: in its title or body, or by its branch (keyword: taken)."""

import re
from typing import AbstractSet

from . import config, ledger

_TRAILING_NUMBER = re.compile(r"[-/](\d+)$")
_ISSUE_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")
_NAME = re.compile(r"(?:[\w.-]+/)?[\w.-]*#\d+")


def names(title: str, body: str, branch: str, repo: config.Repo) -> AbstractSet[str]:
    """The tickets a PR names in its title, body or branch.

    Args:
        title: the PR's title.
        body: the PR's body.
        branch: the PR's head branch.
        repo: the PR's repository, which owns a bare ``#N``.

    Returns:
        The tickets' references.
    """
    text = f"{title}\n{body}"
    found = {ledger.reference(match.group(0), repo) for match in _NAME.finditer(text)}
    found.update(
        f"{match.group(1)}#{match.group(2)}" for match in _ISSUE_URL.finditer(text)
    )
    trailing = _TRAILING_NUMBER.search(branch)
    if trailing:
        found.add(f"{repo.slug}#{trailing.group(1)}")
    return frozenset(found)

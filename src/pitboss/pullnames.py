"""The tickets a PR works on: closed in its title or body, or named by its branch.

The one parse of "which pull request works on ticket T" (plan 4.3, 6.1): a closing
keyword (GitHub's nine) before a reference, or a branch that ends in a number. A
mention in a Plan or an Evidence block names no ticket (keyword: taken, pitboss#448).
"""

import re
from typing import AbstractSet, Protocol, Sequence


class Repository(Protocol):
    """A PR's repository, as far as a reference is spelled (``config.Repo``).

    No import: ``actcore`` takes this module, and its chain of imports is bounded.
    """

    @property
    def owner(self) -> str:
        """Return the user or organisation."""

    @property
    def name(self) -> str:
        """Return the repository's name."""

    @property
    def slug(self) -> str:
        """Return ``owner/name``."""


_TRAILING_NUMBER = re.compile(r"[-/](\d+)$")
_ISSUE_URL = re.compile(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")
# docs: linking a pull request to an issue (the nine closing keywords)
_CLOSING = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?):?\s+(\S+)", re.I)
_NAME = re.compile(r"(?:(?P<owner>[\w.-]+)/)?(?P<name>[\w.-]*)#(?P<number>\d+)")


def _spelled(named: re.Match[str], repo: Repository) -> str:
    # a reference as ``owner/name#number`` (a bare ``#12`` is of the repository)
    owner, called = named["owner"] or repo.owner, named["name"] or repo.name
    return f"{owner}/{called}#{named['number']}"


def closed(text: str, repo: Repository) -> AbstractSet[str]:
    """The tickets a PR's text closes by a closing keyword.

    Args:
        text: the PR's title and body.
        repo: the PR's repository, which owns a bare ``#N``.

    Returns:
        The tickets' references.
    """
    found: set[str] = set()
    for closing in _CLOSING.finditer(text):
        named = _NAME.match(closing.group(1))
        url = _ISSUE_URL.search(closing.group(1))
        if named:
            found.add(_spelled(named, repo))
        elif url:
            found.add(f"{url.group(1)}#{url.group(2)}")
    return frozenset(found)


def written(text: str) -> Sequence[str]:
    """The references a text closes, as written (no repository spells them).

    Args:
        text: the PR's title and body.

    Returns:
        Each reference, in the order of the text.
    """
    found = (_NAME.match(each.group(1)) for each in _CLOSING.finditer(text))
    return [each.group(0) for each in found if each]


def first_closed(text: str, repo: Repository) -> str:
    """The ticket the first closing keyword of a PR's text names.

    Args:
        text: the PR's body.
        repo: the PR's repository, which owns a bare ``#N``.

    Returns:
        The ticket in full, or empty when the text closes none.
    """
    found = (closed(each.group(0), repo) for each in _CLOSING.finditer(text))
    return next((min(each) for each in found if each), "")


def names(title: str, body: str, branch: str, repo: Repository) -> AbstractSet[str]:
    """The tickets a PR closes in its title or body, or names by its branch.

    Args:
        title: the PR's title.
        body: the PR's body.
        branch: the PR's head branch.
        repo: the PR's repository, which owns a bare ``#N``.

    Returns:
        The tickets' references.
    """
    trailing = _TRAILING_NUMBER.search(branch)
    by_branch = {f"{repo.slug}#{trailing.group(1)}"} if trailing else set()
    return frozenset({*closed(f"{title}\n{body}", repo), *by_branch})

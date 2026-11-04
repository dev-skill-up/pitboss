"""The open ticket or PR that a ticket says it cannot be worked on until (pitboss#163).

A ticket states in its body or in a comment ``Cannot be worked on until
<owner/repo#n> has merged`` (or ``Blocked by <owner/repo#n>``). While that
ticket or PR is open the ticket is not work that can be started, so ``slots
next`` and the sweep print ``BLOCKED <ticket> by <owner/repo#n>`` for it and
no ``NEXT`` line (keyword: ticket-blocked). When the blocker closes or merges
the ticket is listed again with no other change.
"""

import re
from typing import AbstractSet, Callable, Iterable, Sequence

from . import config, ghapi, ledger, parsing

# a bare ``#n`` is a ticket of the blocked ticket's own repository
BLOCKER = re.compile(
    r"(?:cannot\s+be\s+worked\s+on\s+until|blocked\s+by)\s+"
    r"((?:[\w.-]+/[\w.-]+)?#\d+)",
    re.IGNORECASE,
)


def named(text: str, repo: config.Repo) -> Sequence[str]:
    """The tickets and PRs a text says it cannot be worked on until.

    Args:
        text: a ticket's body or one of its comments.
        repo: the repository of a bare ``#n``.

    Returns:
        The references as ``owner/name#number``, in the order of the text.
    """
    return [ledger.reference(found, repo) for found in BLOCKER.findall(text)]


def comments_of(
    github: ghapi.GitHub, reference: str, trusted: AbstractSet[str]
) -> Sequence[str]:
    """The comments of a ticket that trusted authors wrote.

    Args:
        github: the API.
        reference: the ticket, ``owner/name#number``.
        trusted: the author associations whose comments count.

    Returns:
        The comments' texts.
    """
    path = "repos/" + reference.replace("#", "/issues/") + "/comments"
    posted = ghapi.pages(github, path, parsing.comments)
    return [each.body for each in posted if each.author_association in trusted]


def open_blocker(
    repo: config.Repo, found: Iterable[str], is_open: Callable[[str], bool]
) -> str:
    """The first blocker that is still open.

    Args:
        repo: the repository of a bare ``#n``.
        found: the texts of the ticket: its body and its comments.
        is_open: whether a ticket or PR, as ``owner/name#number``, is open
            (False when it cannot be read).

    Returns:
        The blocker as ``owner/name#number``, or "" when every one named is
        closed, merged or cannot be read.
    """
    opened = (each for text in found for each in named(text, repo) if is_open(each))
    return next(opened, "")

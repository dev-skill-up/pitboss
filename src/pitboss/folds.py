"""A PR that closes more than one ticket (keyword: fold, pitboss#171).

A rule that caps the open PRs is met by finishing or closing PRs, never by
folding several tickets into one. A body whose ``Fixes`` and ``Closes`` lines
name more than one ticket is refused unless it cites an Opus ruling comment of
that PR (its address) whose ``Ruling:`` line is ``do these steps``.
"""

import re
from typing import AbstractSet, Sequence

from . import flowstate, rulingwords, shapes

CLOSING = re.compile(r"\b(?:Fixes|Closes)\s+((?:[\w.-]+/[\w.-]+)?#\d+)", re.IGNORECASE)
# the comment's address, then its text
Recorded = tuple[str, str]


def tickets(body: str) -> Sequence[str]:
    """The tickets a body says it fixes or closes.

    Args:
        body: the PR body.

    Returns:
        Each ticket once, upper-cased and sorted.
    """
    return sorted({each.upper() for each in CLOSING.findall(body)})


def allows(body: str, rulings: Sequence[Recorded]) -> bool:
    """Whether the body cites an Opus ruling that allows several tickets.

    Args:
        body: the PR body.
        rulings: each recorded comment of the PR, its address and its text.

    Returns:
        True when the body holds the address of a comment that is an Opus
        ruling whose ruling is ``do these steps``.
    """
    return any(
        url in body and flowstate.read_ruling(text) is rulingwords.Ruling.DO_THESE_STEPS
        for url, text in rulings
        if url
    )


def ruling_comments(
    comments: Sequence[shapes.Comment], trusted: AbstractSet[str]
) -> Sequence[Recorded]:
    """The Opus ruling comments of trusted authors.

    Args:
        comments: the comments of a PR.
        trusted: the author associations whose comments count.

    Returns:
        The address and text of each.
    """
    return [
        (each.url, each.body)
        for each in comments
        if flowstate.is_ruling(each.body) and each.author_association in trusted
    ]


def message(named: Sequence[str]) -> str:
    """The finding for a body that closes several tickets.

    Args:
        named: the tickets.

    Returns:
        The finding's text.
    """
    return (
        f"Fixes and Closes name {len(named)} tickets ({', '.join(named)}): one"
        " ticket, one PR; a dependency is its own ticket and PR; several need"
        " an Opus ruling comment (Ruling: do these steps) of this PR, cited by"
        " its address, recorded before the first push"
    )


def folded(body: str, rulings: Sequence[Recorded]) -> Sequence[str]:
    """The tickets of a body that closes several without an allowing ruling.

    Args:
        body: the PR body.
        rulings: each recorded comment of the PR, its address and its text.

    Returns:
        The tickets, none when the body names one or cites a ruling.
    """
    named = tickets(body)
    return named if len(named) > 1 and not allows(body, rulings) else []

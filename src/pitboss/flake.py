"""A p0 ticket about a failing test and its briefs (keyword: flake, pitboss#278).

The lines are the project's (``[slots.brief] flake_worker_lines``,
``flake_review_lines``): the rule they carry is the project's, not pitboss's
(quire's "Quarantine check:" and "Race check:" lines, its Playwright trace).
``quarantine_globs`` names the files whose tests a ticket may mark ``.fixme``.
"""

import enum
import pathlib
import re
from typing import AbstractSet, Iterator, Sequence

from . import donewhen

LABEL = "NOT QUARANTINED"
_NAMES_TEST = re.compile(
    r"\b(?:tests?|specs?|e2e|flaky|flake|flakes|flaking)\b", re.IGNORECASE
)


class Word(enum.Enum):
    """The words a flake ticket is told by.

    Attributes:
        PRIORITY: the label of the tickets that are worked first.
        MARK: what a quarantined test carries.
    """

    PRIORITY = "p0"
    MARK = ".fixme"


def is_flake(labels: AbstractSet[str], title: str, body: str) -> bool:
    """Whether a ticket is a p0 about a test or a flaky run.

    Args:
        labels: the ticket's labels.
        title: its title.
        body: its text.

    Returns:
        True when it carries ``p0`` and its title or Done-when names a test.
    """
    named = f"{title}\n{donewhen.section(body)}"
    return Word.PRIORITY.value in labels and _NAMES_TEST.search(named) is not None


def _cites(text: str, ticket: str) -> bool:
    number = ticket.rpartition("#")[2]
    return re.search(rf"(?:^|[^\w]){re.escape(ticket)}\b|#{number}\b", text) is not None


def _rows(tree: pathlib.Path, globs: Sequence[str]) -> Iterator[str]:
    for pattern in globs:
        for path in sorted(tree.glob(pattern)):
            if path.is_file():
                yield from path.read_text(
                    encoding="utf-8", errors="replace"
                ).splitlines()


def marked(tree: pathlib.Path, globs: Sequence[str], ticket: str) -> bool:
    """Whether a file of the globs has a ``.fixme`` mark citing the ticket.

    Args:
        tree: the checkout the globs are looked up from.
        globs: the files that may hold the mark.
        ticket: the ticket, ``owner/repo#N``.

    Returns:
        True when a line has the mark and the ticket (``#N`` or in full).
    """
    mark = Word.MARK.value
    return any(mark in row and _cites(row, ticket) for row in _rows(tree, globs))


def unmarked_line(ticket: str, tree: pathlib.Path, globs: Sequence[str]) -> str:
    """The line for an open p0 flake ticket whose test is not quarantined.

    Args:
        ticket: the ticket, ``owner/repo#N``.
        tree: the checkout.
        globs: ``quarantine_globs``; none means the project has no such rule.

    Returns:
        The line, or "" when the project lists no files or one has the mark.
    """
    if not globs or marked(tree, globs, ticket):
        return ""
    return (
        f"{LABEL}: {ticket}: a p0 ticket about a failing test, and no"
        f" `{Word.MARK.value}` in {', '.join(globs)} cites it: quarantine the test"
        " first"
    )

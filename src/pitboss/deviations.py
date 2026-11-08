"""The ``Deviations:`` line of a hand-back (keyword: deviations, pitboss#257).

A hand-back has a ``Deviations:`` line (only a departure from the Plan's
commands or the ticket's Done-when, such as ``pitboss nox`` run more than once
on one head; or ``none``, pitboss#345), and a hand-back without it is
``NOT STARTED`` and is sent back. How a file is edited (a heredoc, the Edit
tool, ``sed``), a virtualenv, a redirected output file or a research fetch is
never a deviation.
"""

import dataclasses
import pathlib
from typing import Sequence

from . import config, ledger

PREFIX = "Deviations:"
NOT_STARTED = (
    "NOT STARTED: the hand-back has no `Deviations:` line (only a departure"
    " from the Plan's commands or the ticket's Done-when, or `none`)"
)


def line(handback: str) -> str:
    """The text of the ``Deviations:`` line of a hand-back.

    Args:
        handback: the hand-back text.

    Returns:
        What follows the prefix on the first line that starts with it, stripped;
        empty when there is no such line or nothing follows the prefix.
    """
    for each in handback.splitlines():
        if each.startswith(PREFIX):
            return each[len(PREFIX) :].strip()
    return ""


def not_started(handback: str) -> str:
    """The ``NOT STARTED`` text for a hand-back, empty when it has the line.

    Args:
        handback: the hand-back text.

    Returns:
        The text the orchestrator sends back, empty when the hand-back has a
        ``Deviations:`` line that says something.
    """
    return "" if line(handback) else NOT_STARTED


REVIEW_PREFIX = "Deviation:"


def recorded(review: str) -> Sequence[str]:
    """The deviations a review lists, one for each ``Deviation:`` line.

    Args:
        review: the review comment's text.

    Returns:
        The text after the prefix of each line that starts with it, stripped, in
        order; a line with nothing after the prefix, or ``none``, is left out.
    """
    found = (
        each[len(REVIEW_PREFIX) :].strip()
        for each in review.splitlines()
        if each.startswith(REVIEW_PREFIX)
    )
    return [text for text in found if text and text.lower() != "none"]


def ledger_lines(book: ledger.Ledger) -> Sequence[str]:
    """The ledger's line for each deviation a review listed.

    Args:
        book: the ledger.

    Returns:
        A line for each deviation, ordered by ticket.
    """
    return [
        f"deviation {ticket}: {each}"
        for ticket, listed in sorted(book.deviations.items())
        for each in listed
    ]


def record(
    book: ledger.Ledger, project: config.Repo, ticket: str, name: str
) -> ledger.Ledger | ledger.Refusal:
    """Record the deviations of a review saved in a file on a ticket.

    Args:
        book: the ledger.
        project: the repository of a bare ``#12``.
        ticket: the ticket, as ``slots`` takes it.
        name: the file that holds the review.

    Returns:
        The new ledger, with the deviations not already recorded for the ticket
        after those that are, or a refusal when the file cannot be read.
    """
    try:
        listed = recorded(pathlib.Path(name).read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        return ledger.Refusal(reason=f"{name}: {error}")
    full = ledger.reference(ticket, project)
    kept = dict(book.deviations)
    kept[full] = tuple(dict.fromkeys((*kept.get(full, ()), *listed)))
    return dataclasses.replace(book, deviations=kept)

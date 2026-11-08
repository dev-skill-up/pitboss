"""Scratch named for a ticket whose work is finished (keyword: ticket-closed).

A worktree of a finished ticket leaves its notes beside it (``a1079``,
``s-1079.zip`` for the worktree ``q1079c``). An entry next to a dead checkout
whose name holds the number of that checkout's ticket is dead too, when nothing
in it is live or in use and no work exists only in it (pitboss#348).
"""

import pathlib
from typing import AbstractSet, Sequence

from . import dead, ticketclosed


def ticket_of(wanted: AbstractSet[int], entry: pathlib.Path) -> int:
    """The number in an entry's name that is one of the wanted.

    Args:
        wanted: the ticket numbers of the dead checkouts.
        entry: the entry.

    Returns:
        The first such number, or 0 when the name holds none.
    """
    found = ticketclosed.numbers_in([entry.name])
    return next((number for number in found if number in wanted), 0)


def dead_named(
    look: dead.Look,
    cutoff: float,
    places: AbstractSet[pathlib.Path],
    tickets: Sequence[int],
) -> Sequence[dead.Candidate]:
    """The entries beside the dead checkouts that are named for their tickets.

    A checkout is never one of them (it is judged by its PRs), and a link is
    held by the one safety test.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.
        places: the directories that hold a dead checkout.
        tickets: the numbers in the names of the dead checkouts.

    Returns:
        The candidates.
    """
    wanted = set(tickets)
    entries = (
        (entry, ticket_of(wanted, entry))
        for place in sorted(places)
        for entry in sorted(place.iterdir())
        if not (entry / ".git").exists()
    )
    return dead.present(
        dead.consider(look, entry, f"named for ticket {number}, finished", cutoff)
        for entry, number in entries
        if number
    )

"""The reading of the PRs and the agents that hold a slot (keyword: slot-held).

The facts and the lines are ``slotheld``'s (pitboss#291).
"""

import argparse
from typing import AbstractSet, Iterable, Sequence

from . import ledger, pulls, slotheld, slotholder, work

HOLDING = (
    work.Category.FIX_REVIEW,
    work.Category.FIRST_ROUND,
    work.Category.RULING_STEPS,
    work.Category.RESOLVE_CONFLICT,
)


def _recorded(book: ledger.Ledger) -> Iterable[ledger.Slot]:
    return (slot for slot in book.slots if slot.agent)


def derived(book: ledger.Ledger, running: Iterable[str] | None) -> ledger.Ledger:
    """The ledger as the live agents make it: a slot holds an agent only if it runs.

    The ledger is kept by hand, so a line for an agent that finished must not
    make a slot look full, nor a missing line for a running agent make it look
    empty (pitboss#94). With no ``--running`` the agents are not known and the
    ledger stands as it is; ``occupy`` then says no slot is computed.

    Args:
        book: the ledger.
        running: the names of the agents the session runs, or None when not given.

    Returns:
        The ledger with every slot whose agent does not run emptied.
    """
    if running is None:
        return book
    return _only(book, frozenset(running))


def live(
    args: argparse.Namespace,
    book: ledger.Ledger,
    done: AbstractSet[str] = frozenset(),
) -> ledger.Ledger:
    """The ledger as the agents named by ``--running`` make it.

    Args:
        args: the parsed arguments; a command with no ``--running`` keeps the book.
        book: the ledger.
        done: the agents that handed back (keyword: hand-back-done): their slots
            are empty whether the harness lists them as running or not.

    Returns:
        ``derived`` of the book and the running agents, less the slots of ``done``.
    """
    book = derived(book, getattr(args, "running", None))
    return _only(book, frozenset(each.agent for each in book.slots) - done)


def _only(book: ledger.Ledger, alive: AbstractSet[str]) -> ledger.Ledger:
    return slotholder.without(book, slotholder.agents(book) - {"", *alive})


def holding(
    facts: Iterable[pulls.PullFacts], book: ledger.Ledger
) -> Sequence[slotheld.Held]:
    """The PRs whose next step holds a slot that no ledger row records.

    Args:
        facts: the open PRs.
        book: the ledger; an agent whose task is the PR, or a ticket the PR
            names, already holds its slot.

    Returns:
        The PRs, in the order given.
    """
    tasks = frozenset(slot.task for slot in _recorded(book))
    found = []
    for pull in facts:
        category = work.category_of(pull)
        if category not in HOLDING:
            continue
        if tasks & (work.taken([pull]) | {pulls.reference(pull)}):
            continue
        found.append(
            slotheld.Held(
                reference=pulls.reference(pull), step=work.CATEGORY_WORDS[category]
            )
        )
    return found


def unrecorded(book: ledger.Ledger, running: Iterable[str] | None) -> Sequence[str]:
    """The live agents that hold no slot, when more run than slots hold.

    Args:
        book: the ledger.
        running: the names of the agents the session runs, or None when not given.

    Returns:
        The names of the running agents the ledger does not hold; none unless
        the live agents outnumber the recorded slots.
    """
    live = list(dict.fromkeys(running or ()))
    recorded = {slot.agent for slot in _recorded(book)}
    if len(live) <= len(recorded):
        return []
    return [name for name in live if name not in recorded]


def occupy(
    facts: Iterable[pulls.PullFacts],
    book: ledger.Ledger,
    running: Iterable[str] | None,
) -> slotheld.Occupancy:
    """What holds the slots beyond the ledger's agents.

    Args:
        facts: the open PRs (none when they were not read).
        book: the ledger, as ``derived`` makes it.
        running: the names of the agents the session runs, or None.

    Returns:
        The occupancy; with no ``running`` the agents are not known, so no slot
        is held or empty and the occupancy says so (``known`` is False).
    """
    if running is None:
        return slotheld.Occupancy(known=False)
    return written(facts, book, running)


def written(
    facts: Iterable[pulls.PullFacts],
    book: ledger.Ledger,
    running: Iterable[str] | None,
) -> slotheld.Occupancy:
    """What holds the slots, counting the ledger's rows as they are written.

    Args:
        facts: the open PRs (none when they were not read).
        book: the ledger.
        running: the names of the agents the session runs, or None.

    Returns:
        The occupancy.
    """
    empty = sum(1 for slot in book.slots if not slot.agent)
    # a ledger with no empty slot has none for a round to hold
    held = holding(facts, book) if empty else []
    loose = unrecorded(book, running)
    return slotheld.Occupancy(
        holding=held,
        unrecorded=loose,
        free=0 if loose else max(0, empty - len(held)),
        references=frozenset() if loose else frozenset(h.reference for h in held),
    )

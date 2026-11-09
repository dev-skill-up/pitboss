"""The reading of the PRs and the agents that hold a slot (keyword: slot-held).

The facts and the lines are ``slotheld``'s (pitboss#291).
"""

import argparse
import dataclasses
from typing import AbstractSet, Iterable, Sequence

from . import ledger, pulls, slotheld, work

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
    alive = frozenset(running)
    slots = tuple(_if_running(slot, alive) for slot in book.slots)
    return dataclasses.replace(book, slots=slots)


def _if_running(slot: ledger.Slot, alive: AbstractSet[str]) -> ledger.Slot:
    if not slot.agent or slot.agent in alive:
        return slot
    return ledger.Slot(name=slot.name, model=slot.model)


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


def counted(
    offer: work.Offered,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
    args: argparse.Namespace,
) -> work.Offered:
    """The offered work, with what holds the slots beyond the ledger's agents.

    Args:
        offer: the queued work (``offering.offered``).
        opened: the open PRs, read or not.
        book: the ledger.
        args: the parsed arguments; ``running`` names the agents the session runs.

    Returns:
        The offer with its occupancy.
    """
    running = getattr(args, "running", None)
    taken = occupy(pulls.readable(opened), book, running)
    return dataclasses.replace(offer, occupancy=taken)

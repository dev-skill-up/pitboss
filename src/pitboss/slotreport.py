"""The ledger's lines: each slot and what its empty ones are for (slot-held)."""

import sys
from typing import Sequence

from . import deviations, ledger, slotheld
from .markers import Marker


def slot_lines(book: ledger.Ledger, taken: slotheld.Occupancy) -> Sequence[str]:
    """The ledger, with a loud line for each empty slot that is free.

    An empty slot that a PR's round or an unrecorded agent holds is not free:
    its row says so, and ``SLOT HELD`` and ``UNRECORDED AGENT`` lines follow
    (keyword: slot-held, pitboss#291). When the agents are not known no slot row
    is printed, only the line that says so (pitboss#94).

    Args:
        book: the ledger.
        taken: what holds the slots beyond the ledger's agents.

    Returns:
        The lines.
    """
    if not taken.known:
        return [*slotheld.lines(taken), *deviations.ledger_lines(book)]
    free = taken.free
    found = []
    for slot in book.slots:
        if not slot.agent:
            free -= 1
        found.append(_slot_line(slot) if slot.agent or free >= 0 else _held_row(slot))
    if all(slot.agent for slot in book.slots):
        found.append("slots: the ledger says all full")
    return [*found, *slotheld.lines(taken), *deviations.ledger_lines(book)]


def _held_row(slot: ledger.Slot) -> str:
    return (
        f"slot {slot.name} ({slot.model}): empty, but held by work the ledger"
        " does not record"
    )


def _slot_line(slot: ledger.Slot) -> str:
    name = f"{slot.name} ({slot.model})"
    if slot.agent:
        state = ", waiting" if slot.waiting else ""
        return f"slot {name}: {slot.task} ({slot.agent}{state})"
    return (
        f"{Marker.EMPTY_SLOT.text}: {name}: run 'pitboss slots next' and start its line"
    )


def print_free_slots(queued: int, taken: slotheld.Occupancy) -> None:
    """Print the line that says slots are free while work is queued.

    Args:
        queued: how many items are queued.
        taken: what holds the slots beyond the ledger's agents.
    """
    free = taken.free
    if taken.known and free and queued:
        print(
            f"{Marker.SLOTS_FREE.text} {free}: {queued} queued; a wake-up"
            " (send_later) is required before this turn ends, or nothing starts them"
        )


def print_ledger(book: ledger.Ledger, taken: slotheld.Occupancy) -> None:
    """Print the ledger, and on stderr the reminder to check it.

    Args:
        book: the ledger.
        taken: what holds the slots beyond the ledger's agents.
    """
    for line in slot_lines(book, taken):
        print(line)
    print(CHECK_LEDGER_LINE, file=sys.stderr)


CHECK_LEDGER_LINE = (
    f"{Marker.CHECK_BEFORE_YOU_ANSWER.text}: the ledger is kept by hand. List the"
    " agents the session runs, run 'pitboss slots check CONFIG --running NAME ...',"
    " fix the ledger with 'slots free' and 'slots set', then act or answer."
)

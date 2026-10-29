"""Agents the ledger holds that have said nothing since they were started."""

import datetime
from typing import Sequence

from . import ledger, slotlog
from .markers import Marker

SILENT_MINUTES = 10


def silent_minutes(slot: ledger.Slot, now: datetime.datetime) -> int | None:
    """How long a slot's agent has been silent, when it is overdue.

    Args:
        slot: the slot.
        now: the time now.

    Returns:
        The whole minutes since it started, or None when the slot has no agent
        or no start time, the agent has handed back or notified, or it was
        started no more than ``SILENT_MINUTES`` ago.
    """
    if not slot.agent or not slot.started or slot.heard:
        return None
    elapsed = slotlog.utc(now) - slotlog.utc(
        datetime.datetime.fromisoformat(slot.started)
    )
    minutes = int(elapsed.total_seconds() // 60)
    return minutes if elapsed > datetime.timedelta(minutes=SILENT_MINUTES) else None


def lines(book: ledger.Ledger, now: datetime.datetime) -> Sequence[str]:
    """The ``NO HAND-BACK`` lines of a ledger.

    Args:
        book: the ledger.
        now: the time now.

    Returns:
        A line for each agent started more than ``SILENT_MINUTES`` ago that has
        produced no hand-back or notification.
    """
    found = [(slot, silent_minutes(slot, now)) for slot in book.slots]
    return [
        f"{Marker.NO_HAND_BACK.text} {slot.agent} ({minutes} minutes)"
        for slot, minutes in found
        if minutes is not None
    ]


def print_lines(book: ledger.Ledger, now: datetime.datetime) -> None:
    """Print the ``NO HAND-BACK`` lines of a ledger.

    Args:
        book: the ledger.
        now: the time now.
    """
    for line in lines(book, now):
        print(line)

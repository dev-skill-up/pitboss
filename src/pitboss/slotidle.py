"""Slots that stayed empty while the sweep named ready work (keyword: slot-idle)."""

import datetime
from typing import Sequence

from . import ledger, slotlog
from .markers import Marker

IDLE_MINUTES = 2


def idle_minutes(
    slot: ledger.Slot,
    entries: Sequence[slotlog.Entry],
    now: datetime.datetime,
    over: int = IDLE_MINUTES,
) -> int | None:
    """How long an empty slot has been empty, when that is over ``over`` minutes.

    The time comes from the slot log (pitboss#17): the time of the slot's newest
    entry, which must say the slot is empty. A slot the log has not seen has no
    time, and so none is told.

    Args:
        slot: the slot.
        entries: the slot log, in file order.
        now: the time now.
        over: the minutes it must have been empty for more than (``free-check``
            passes ten; keyword: free-check, pitboss#450).

    Returns:
        The whole minutes since the slot was emptied, or None when it has an
        agent, the log has no empty entry for it as its newest, or it has been
        empty for no more than ``over`` minutes (``IDLE_MINUTES`` unless given).
    """
    mine = [entry for entry in entries if entry.slot == slot.name]
    if slot.agent or not mine:
        return None
    newest = max(enumerate(mine), key=lambda pair: (pair[1].time, pair[0]))[1]
    if newest.state is not slotlog.State.EMPTY:
        return None
    elapsed = slotlog.utc(now) - newest.time
    minutes = int(elapsed.total_seconds() // 60)
    return minutes if elapsed > datetime.timedelta(minutes=over) else None


def lines(
    book: ledger.Ledger, entries: Sequence[slotlog.Entry], now: datetime.datetime
) -> Sequence[str]:
    """The ``SLOT IDLE`` lines of a ledger; the caller says work is queued.

    Args:
        book: the ledger.
        entries: the slot log.
        now: the time now.

    Returns:
        A line for each slot empty for over ``IDLE_MINUTES``.
    """
    found = [(slot, idle_minutes(slot, entries, now)) for slot in book.slots]
    return [
        f"{Marker.SLOT_IDLE.text} {slot.name} ({minutes} minutes): start the item"
        f" of its {Marker.EMPTY_SLOT.text} line now; a wait line is no reason to"
        " leave a slot empty"
        for slot, minutes in found
        if minutes is not None
    ]

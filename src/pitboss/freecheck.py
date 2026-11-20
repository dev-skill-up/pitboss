"""``slots free-check``: a free slot nothing was dispatched for (free-check).


The existing ``SLOT IDLE`` line needs queued work and two minutes; this one is
about the slot alone: ten minutes free by the slot log, whatever the queue holds
(pitboss#415 is the design it extends).
"""

import datetime
from typing import Callable, Iterable, TypeVar

from . import ledger, nextfound, slotholding, slotidle, slotlog
from .markers import Marker

FREE_MINUTES = 10
Found = TypeVar("Found", bound=nextfound.Found)


def minutes(
    book: ledger.Ledger, entries: Iterable[slotlog.Entry], now: datetime.datetime
) -> int | None:
    """How long the longest-free slot has been free, when that is over ten minutes.

    Args:
        book: the ledger as the live agents make it.
        entries: the slot log.
        now: the time now.

    Returns:
        The whole minutes, or None when no slot is free for over ``FREE_MINUTES``.
    """
    kept = list(entries)
    waits = (
        slotidle.idle_minutes(slot, kept, now, FREE_MINUTES) for slot in book.slots
    )
    return max(filter(None, waits), default=None)


def line(
    found: Found,
    first: Callable[[Found], str],
) -> str | None:
    """The ``IDLE SLOT`` line of ``sweep`` and ``slots free-check``, when it applies.

    Args:
        found: the context.
        first: says the first decision (``onepath.first_line``); called only when
            the line applies.

    Returns:
        ``IDLE SLOT: free for N minutes, next is <the slots next line>``, or
        None when every slot is held or free for ten minutes or less.
    """
    book = slotholding.derived(ledger.configured(found.settings), found.args.running)
    log = found.settings.slots.log
    waited = minutes(book, slotlog.read(log), found.now)
    if waited is None:
        return None
    return f"{Marker.IDLE_SLOT.text}: free for {waited} minutes, next is " + first(
        found
    )

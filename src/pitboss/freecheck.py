"""``slots free-check``: a free slot nothing was dispatched for (free-check).


The existing ``SLOT IDLE`` line needs queued work and two minutes; this one is
about the slot alone: ten minutes free by the slot log, whatever the queue holds
(pitboss#415 is the design it extends).
"""

import datetime
from typing import Callable, Iterable, Sequence

from . import ledger, nextfound, pulls, slotholding, slotidle, slotlog
from .markers import Marker

FREE_MINUTES = 10


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
    found: nextfound.Found,
    opened: Callable[[], Sequence[pulls.Read]],
    first: Callable[[nextfound.Found, Sequence[pulls.Read], ledger.Ledger], str],
) -> str | None:
    """The ``IDLE SLOT`` line of ``sweep`` and ``slots free-check``, when it applies.

    Args:
        found: the context.
        opened: reads the open PRs; called only when the line applies.
        first: says the first startable item (``nextlist.first_startable``).

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
        found, opened(), book
    )

"""The ``SLOT FREE`` line of ``slots watch`` (keyword: one-path)."""

from typing import Callable

from . import ledger, nextfound, slotlog, slotsheader
from .markers import Marker


def line(
    first: Callable[[nextfound.Found], str],
    found: nextfound.Found,
    book: ledger.Ledger,
    cap: int,
) -> str:
    """The ``SLOT FREE`` line of ``slots watch``, naming the first decision.

    Args:
        first: the first decision's line (``onepath.first_line``).
        found: the context.
        book: the ledger.
        cap: the slots configured.

    Returns:
        The line.
    """
    since = slotsheader.free_since(book, found.settings.slots.log, found.now)
    free = cap - len(slotsheader.running(book))
    return (
        f"{Marker.WATCH_SLOT_FREE.text}: {free} of {cap} free since"
        f" {slotlog.utc(since).strftime(slotsheader.TIME_FORMAT)}; first startable:"
        f" {first(found)}"
    )

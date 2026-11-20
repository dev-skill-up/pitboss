"""The running agents of a ledger, how each is named, and when a slot was freed.

The ``SLOTS``, ``RUNNING``, ``FREE SLOT``, ``START`` and ``LEDGER STALE`` lines
of ``slots next`` are retired (keyword: one-path): its answer is the decisions
and the free slots as a datum of it.
"""

import datetime
import pathlib
from typing import Sequence

from . import ledger, slotlog

KIND_WORDS = {
    "start": "worker",
    "review": "reviewer",
    "fix": "fix round",
    "ruling": "ruling",
}
DEFAULT_KIND = "start"
TIME_FORMAT = "%Y-%m-%d %H:%MZ"


def running(book: ledger.Ledger) -> Sequence[ledger.Slot]:
    """The slots that hold an agent.

    Args:
        book: the ledger.

    Returns:
        The slots, in order.
    """
    return [slot for slot in book.slots if slot.agent]


def subject(slot: ledger.Slot) -> str:
    """The ticket or PR an agent is named by.

    Args:
        slot: its slot.

    Returns:
        The ticket for a worker, the PR for a round or a review.
    """
    # a worker is named by its ticket, a round or a review by its PR
    if (slot.kind or DEFAULT_KIND) == DEFAULT_KIND:
        return slot.ticket or slot.task or slot.agent
    return slot.task or slot.ticket or slot.agent


def free_since(
    book: ledger.Ledger, log: pathlib.Path, now: datetime.datetime
) -> datetime.datetime:
    """When the oldest free slot was freed, by the slot log.

    Args:
        book: the ledger.
        log: the slot log file.
        now: the time now, for a slot the log has not seen.

    Returns:
        The earliest time of the newest ``EMPTY`` entry of an empty slot; now
        when the log has none.
    """
    empty = {slot.name for slot in book.slots if not slot.agent}
    newest: dict[str, slotlog.Entry] = {}
    for entry in slotlog.read(log):
        if entry.slot in empty:
            newest[entry.slot] = entry
    times = [each.time for each in newest.values() if each.state is slotlog.State.EMPTY]
    return min(times, default=slotlog.utc(now))

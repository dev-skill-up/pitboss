"""The first lines of ``slots next``: who runs, the cap, the free slots (slots-header).

The orchestrator composed "the next slot goes to X" from memory and let a slot sit
empty after a hand-back (pitboss#415), so the first lines of the list say it:
``SLOTS`` (the count against the cap and the free slots), a ``RUNNING`` line for
each agent by kind, and, below the cap, ``FREE SLOT`` and ``START``.
"""

import datetime
import pathlib
from typing import Sequence

from . import ledger, slotlog
from .markers import Marker

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


def _subject(slot: ledger.Slot) -> str:
    # a worker is named by its ticket, a round or a review by its PR
    if (slot.kind or DEFAULT_KIND) == DEFAULT_KIND:
        return slot.ticket or slot.task or slot.agent
    return slot.task or slot.ticket or slot.agent


def running_line(slot: ledger.Slot) -> str:
    """The ``RUNNING`` line of one agent.

    Args:
        slot: its slot.

    Returns:
        ``RUNNING worker <ticket>``, ``RUNNING fix round <PR>``, ``RUNNING
        reviewer <PR>`` or ``RUNNING ruling <task>``.
    """
    word = KIND_WORDS.get(slot.kind or DEFAULT_KIND, slot.kind)
    return f"{Marker.RUNNING.text} {word} {_subject(slot)}"


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


def _free_names(book: ledger.Ledger) -> str:
    names = [slot.name for slot in book.slots if not slot.agent]
    return ", ".join(names) or "none"


def lines(
    book: ledger.Ledger,
    cap: int,
    since: datetime.datetime,
    start: str | None,
) -> Sequence[str]:
    """The ``SLOTS``, ``RUNNING``, ``FREE SLOT`` and ``START`` lines.

    Args:
        book: the ledger as the live agents make it.
        cap: the number of slots (``[slots] default``).
        since: when the oldest free slot was freed.
        start: the first dispatchable ``NEXT`` line, or None when nothing is queued.

    Returns:
        The lines: the count and the free slots, one line for each running agent,
        and below the cap ``FREE SLOT`` and the ``START`` line.
    """
    busy = running(book)
    found = [
        f"{Marker.SLOTS.text} {len(busy)} of {cap}, free: {_free_names(book)}",
        *map(running_line, busy),
    ]
    if len(busy) >= cap:
        return found
    found.append(free_slot_line(cap - len(busy), cap, since))
    return [*found, *([f"{Marker.START.text} {start}"] if start else [])]


def free_slot_line(free: int, cap: int, since: datetime.datetime) -> str:
    """The ``FREE SLOT`` line.

    Args:
        free: how many slots are free.
        cap: the number of slots.
        since: when the oldest free slot was freed.

    Returns:
        The line.
    """
    return (
        f"{Marker.FREE_SLOT.text}: {free} of {cap} free since"
        f" {slotlog.utc(since).strftime(TIME_FORMAT)}; dispatch before reading"
        " anything else"
    )


def stale_line(book: ledger.Ledger, written: pathlib.Path) -> Sequence[str]:
    """The ``LEDGER STALE`` line of a read that was told no running agents.

    Args:
        book: the ledger as written.
        written: the ledger file.

    Returns:
        One line when a row holds an agent, else none.
    """
    rows = len(running(book))
    if not rows:
        return []
    when = datetime.datetime.fromtimestamp(written.stat().st_mtime, datetime.UTC)
    return [
        f"{Marker.LEDGER_STALE.text}: last written {when.strftime(TIME_FORMAT)},"
        f" {rows} rows name agents nobody has confirmed"
    ]

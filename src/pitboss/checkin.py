"""The orchestrator's check-in, a status post every 30 minutes (check-in, pitboss#450).


The ledger keeps the time of the last one (``slots checkin``), so a lapse is seen
by ``slots next`` and ``sweep`` even when the session that held the timer is gone.
A timer that expires after 7 days is why each firing recreates its own schedule.
"""

import dataclasses
import datetime
from typing import Iterable, Sequence

from . import ledger, slotlog
from .markers import Marker

OVERDUE_MINUTES = 30
EXPIRY_DAYS = 7


def record(book: ledger.Ledger, now: datetime.datetime) -> ledger.Ledger:
    """The ledger with a check-in just now.

    Args:
        book: the ledger.
        now: the time now.

    Returns:
        The ledger.
    """
    return dataclasses.replace(book, checkin=now.isoformat())


def queue_text(references: Sequence[str], given: str) -> str:
    """Name the first queued item and its command, for ``IDLE SLOT``.

    Args:
        references: the queued items, in order.
        given: the configuration as the command was given it.

    Returns:
        The item with its ``slots next`` command, or that nothing is queued.
    """
    if not references:
        return "no open ticket or PR is queued: file the next ticket"
    return f"{references[0]} (pitboss slots next {references[0]} --config {given})"


def say(lines: Iterable[str | None]) -> None:
    """Print the lines that are there.

    Args:
        lines: lines, or None for one that does not apply.
    """
    for each in lines:
        if each:
            print(each)


def overdue(book: ledger.Ledger, now: datetime.datetime) -> str | None:
    """The ``CHECK-IN OVERDUE`` line, when the last check-in is over 30 minutes.

    Args:
        book: the ledger.
        now: the time now.

    Returns:
        The line, or None when no check-in is recorded or the last is recent.
    """
    if not book.checkin:
        return None
    last = slotlog.utc(datetime.datetime.fromisoformat(book.checkin))
    elapsed = slotlog.utc(now) - last
    if elapsed <= datetime.timedelta(minutes=OVERDUE_MINUTES):
        return None
    minutes = int(elapsed.total_seconds() // 60)
    return f"{Marker.CHECK_IN_OVERDUE.text}: last {minutes} minutes ago"


PROMPT = f"""\
Status post, every {OVERDUE_MINUTES} minutes. Each firing of this timer does these \
steps, in order:
1. Run `pitboss sweep --config CONFIG` and act on its first line if it is IDLE SLOT or \
CHECK-IN OVERDUE.
2. Post one status message to the thread that says: what holds each slot (the \
agent and its ticket or PR), what changed since the last post, what is blocked \
on what, when this timer is next due, and when it expires.
3. Record the check-in: run \
`pitboss slots checkin --config CONFIG`. The ledger keeps its time, and \
`slots next` and `sweep` print CHECK-IN OVERDUE when the last one is over \
{OVERDUE_MINUTES} minutes old.
4. Recreate your own schedule fresh: create a new timer for the next \
{OVERDUE_MINUTES} minutes, then delete the one that fired. A timer expires \
{EXPIRY_DAYS} days after it was made, so never rely on one timer that can lapse: \
every firing makes the next from now, and the post names the new expiry.
"""

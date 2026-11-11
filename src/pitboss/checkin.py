"""The orchestrator's check-in, a status post every 30 minutes (check-in, pitboss#450).


The ledger keeps the time of the last one (``slots checkin``), so a lapse is seen
by ``slots next`` and ``sweep`` even when the session that held the timer is gone.
A timer that expires after 7 days is why each firing recreates its own schedule.
"""

import dataclasses
import datetime
from typing import Iterable

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


def renew(book: ledger.Ledger, now: datetime.datetime) -> ledger.Ledger:
    """Say a lapse before this check-in, then record the check-in.

    A firing records its check-in before its sweep runs, so the sweep never
    flags the firing itself; the lapse before it is said here.

    Args:
        book: the ledger.
        now: the time now.

    Returns:
        The ledger with a check-in just now.
    """
    say([overdue(book, now)])
    return record(book, now)


PROMPT = f"""\
Status post, every {OVERDUE_MINUTES} minutes. Each firing of this timer does these \
steps, in order:
1. Record the check-in first: run `pitboss slots checkin --config CONFIG`. The \
ledger keeps its time. It prints CHECK-IN OVERDUE when the check-in before this one \
was over {OVERDUE_MINUTES} minutes ago, and `slots next` and `sweep` print it \
the same way when no firing records one.
2. Run `pitboss sweep --config CONFIG` and act on its first line if it is IDLE SLOT \
or CHECK-IN OVERDUE.
3. Post one status message to the thread that says: what holds each slot (the \
agent and its ticket or PR), what changed since the last post, what is blocked \
on what, when this timer is next due, and when it expires.
4. Keep the timer you have: it is one kept cron job, never one made again at each \
firing, because each new job gets a random offset. Run CronList and create a job \
only if it shows none. Re-arm the job once a day, so it never nears the \
{EXPIRY_DAYS} days after which a timer expires, and the post names its expiry.
"""

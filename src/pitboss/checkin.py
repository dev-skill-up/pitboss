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


def _utc(text: str) -> datetime.datetime:
    return slotlog.utc(datetime.datetime.fromisoformat(text))


def record(book: ledger.Ledger, now: datetime.datetime) -> ledger.Ledger:
    """The ledger with a check-in just now.

    Args:
        book: the ledger.
        now: the time now.

    Returns:
        The ledger.
    """
    late = overdue(book, now)
    since = book.checkin_since if book.checkin and not late else now.isoformat()
    return dataclasses.replace(book, checkin=now.isoformat(), checkin_since=since)


def status_line(book: ledger.Ledger) -> str:
    """The line to paste into the status: the check-in, the next one and the expiry.

    (Keyword: checkin-status-from-state, pitboss#471.) The times are the clock's at
    the firing, never typed from memory; the next one is 30 minutes after it, and
    the job expires 7 days after its run of check-ins began.

    Args:
        book: the ledger, with the check-in just recorded.

    Returns:
        ``check-in HH:MMZ; next due HH:MMZ; job expires YYYY-MM-DDTHH:MMZ``.
    """
    now, since = _utc(book.checkin), _utc(book.checkin_since)
    due = now + datetime.timedelta(minutes=OVERDUE_MINUTES)
    expires = since + datetime.timedelta(days=EXPIRY_DAYS)
    return (
        f"check-in {now:%H:%M}Z; next due {due:%H:%M}Z;"
        f" job expires {expires:%Y-%m-%dT%H:%M}Z"
    )


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
    minutes = slotlog.minutes_over(book.checkin, now, OVERDUE_MINUTES)
    if minutes is None:
        return None
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
steps, in order, and posts no line of its own:
1. Run `pitboss slots checkin --config CONFIG`. It records the check-in and prints \
CHECK-IN OVERDUE when the check-in before this one was over {OVERDUE_MINUTES} \
minutes ago, the ledger, and the line with the real time of the firing, the next \
due time and the expiry.
2. Run `pitboss sweep --config CONFIG` and act on its first line if it is IDLE SLOT \
or CHECK-IN OVERDUE.
3. Run `pitboss slots tasklist --config CONFIG`. Post, as they are printed, the \
line of step 1 and the task list: every running agent, open PR and queued item \
comes from the ledger and GitHub, so the status has no text of yours.
4. Keep the timer you have: run CronList and create a job only if it shows none. \
Re-arm it once a day, before the {EXPIRY_DAYS} days after which a timer expires.
"""

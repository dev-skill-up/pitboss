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
        The ledger; its first check-in is kept until the job is made again.
    """
    first = book.checkin_first or now.isoformat()
    return dataclasses.replace(book, checkin=now.isoformat(), checkin_first=first)


def status_line(book: ledger.Ledger, now: datetime.datetime) -> str:
    """The line to paste into the status: this firing, the next, the expiry.

    The times are computed from the clock and the ledger, never typed (keyword:
    check-in, pitboss#471). The job was made at most one interval before its
    first firing, so the expiry counted from there is never later than the
    real one.

    Args:
        book: the ledger, with this check-in recorded.
        now: the time now.

    Returns:
        ``check-in 10:21Z; next due 10:51Z; job expires 2026-11-18T04:22Z``.
    """
    here = slotlog.utc(now)
    first = slotlog.utc(
        datetime.datetime.fromisoformat(book.checkin_first or now.isoformat())
    )
    interval = datetime.timedelta(minutes=OVERDUE_MINUTES)
    expires = first - interval + datetime.timedelta(days=EXPIRY_DAYS)
    return (
        f"check-in {here:%H:%M}Z; next due {here + interval:%H:%M}Z;"
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
    last = slotlog.utc(datetime.datetime.fromisoformat(book.checkin))
    elapsed = slotlog.utc(now) - last
    if elapsed <= datetime.timedelta(minutes=OVERDUE_MINUTES):
        return None
    minutes = int(elapsed.total_seconds() // 60)
    return f"{Marker.CHECK_IN_OVERDUE.text}: last {minutes} minutes ago"


def _said(book: ledger.Ledger, made: ledger.Ledger, now: datetime.datetime) -> None:
    say([overdue(book, now), status_line(made, now)])


def renew(book: ledger.Ledger, now: datetime.datetime) -> ledger.Ledger:
    """Record this check-in, then say a lapse before it and the status line.

    A firing records its check-in before its sweep runs, so the sweep never
    flags the firing itself; the lapse before it is said here.

    Args:
        book: the ledger.
        now: the time now.

    Returns:
        The ledger with a check-in just now.
    """
    made = record(book, now)
    _said(book, made, now)
    return made


def rearm(book: ledger.Ledger, now: datetime.datetime) -> ledger.Ledger:
    """``renew`` for a timer job that was made again: its expiry counts from here.

    Args:
        book: the ledger.
        now: the time now.

    Returns:
        The ledger with a check-in just now and no earlier first one.
    """
    made = record(dataclasses.replace(book, checkin_first=""), now)
    _said(book, made, now)
    return made


PROMPT = f"""\
Status post, every {OVERDUE_MINUTES} minutes. This prompt holds commands only; \
every fact of the status is the output of a command, never a line written here \
or from memory. Each firing of this timer does these steps, in order:
1. Record the check-in first: run `pitboss slots checkin --config CONFIG`. The \
ledger keeps its time. It prints CHECK-IN OVERDUE when the check-in before this one \
was over {OVERDUE_MINUTES} minutes ago, and the line with this firing, the next due \
time and the expiry of the job.
2. Run `pitboss sweep --config CONFIG` and act on its first line if it is IDLE SLOT \
or CHECK-IN OVERDUE.
3. Run `pitboss slots tasklist --config CONFIG` and post its output as it is, as the \
status and as the checklist: the running agents, the merged PRs and what waits with \
its next step, under a header that holds the times. Add no line of your own.
4. Keep the timer you have: it is one kept cron job, never one made again at each \
firing, because each new job gets a random offset. Run CronList and create a job \
only if it shows none, then run `pitboss slots checkin --config CONFIG --rearmed`. \
The job expires {EXPIRY_DAYS} days after it is made: re-arm it once a day.
"""

"""``slots report`` and ``slots time``: the slot log over a window of time."""

import datetime
import sys
from typing import Callable, Sequence

from . import nextfound, slotlog

Lines = Callable[
    [Sequence[slotlog.Entry], datetime.datetime, datetime.datetime], Sequence[str]
]


def _window(found: nextfound.Found, word: str, make: Lines) -> Sequence[str]:
    # the lines of the log from --since to --until, the whole log by default
    if found.args.words:
        print(f"slots {word} takes no words", file=sys.stderr)
        raise SystemExit(2)
    entries = slotlog.read(found.settings.slots.log)
    since = (
        slotlog.utc(datetime.datetime.fromisoformat(found.args.since))
        if found.args.since
        else min((entry.time for entry in entries), default=slotlog.utc(found.now))
    )
    until = (
        slotlog.utc(datetime.datetime.fromisoformat(found.args.until))
        if found.args.until
        else slotlog.utc(found.now)
    )
    return make(entries, since, until)


def report(found: nextfound.Found) -> None:
    """Print the share of slot time in each state.

    Args:
        found: the context.
    """
    for line in _window(found, "report", slotlog.lines):
        print(line)


def worked(found: nextfound.Found) -> None:
    """Print the worker minutes of each ticket.

    Args:
        found: the context.
    """
    for line in _window(found, "time", slotlog.ticket_lines):
        print(line)

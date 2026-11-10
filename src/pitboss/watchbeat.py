"""The watcher's heartbeat and the sweep's line when it is missing (slots-watch)."""

import datetime
import pathlib
from typing import Sequence

from .markers import Marker

HEARTBEAT = ".watch"
MISSED_ROUNDS = 3


def heartbeat_path(book: pathlib.Path) -> pathlib.Path:
    """The file a watcher touches each round.

    Args:
        book: the ledger file.

    Returns:
        Its path, beside the ledger.
    """
    return book.with_name(book.name + HEARTBEAT)


def beat(book: pathlib.Path, now: datetime.datetime, interval: int) -> None:
    """Record that a watcher is alive.

    Args:
        book: the ledger file.
        now: the time now.
        interval: the seconds between its rounds.
    """
    heartbeat_path(book).write_text(f"{now.isoformat()} {interval}\n")


def missing_line(
    book: pathlib.Path, now: datetime.datetime, given: str
) -> Sequence[str]:
    """The sweep's line when no watcher beats.

    Args:
        book: the ledger file.
        now: the time now.
        given: the configuration as the command was given it.

    Returns:
        The line with the Monitor invocation, or none when a watcher beat within
        three of its intervals.
    """
    path = heartbeat_path(book)
    if path.exists():
        when, _, seconds = path.read_text().partition(" ")
        late = now - datetime.datetime.fromisoformat(when)
        if late <= datetime.timedelta(seconds=MISSED_ROUNDS * int(seconds)):
            return []
    return [
        f"{Marker.WATCH_MISSING.text}: no slots watch is running, so the ledger"
        " drifts; start it with the Monitor tool: Monitor(command="
        f'"pitboss slots watch --config {given}", description="slot ledger",'
        " persistent=true)"
    ]

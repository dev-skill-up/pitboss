"""The ``LOG`` lines of a sweep: each hand-back and each clean-up, said once.

Owner, 2026-11-08: each hand-back and each disk clean-up is documented, or it
is impossible to know what is going on (pitboss#347). ``slots free`` records a
hand-back, and every command that removes something records a clean-up, in an
events file beside the slot log. ``sweep``, ``next`` and ``slots next`` print a
``LOG`` line for each event not yet posted, and mark them posted, so a line is
printed once. The orchestrator posts each ``LOG`` line to the owner as it is.
"""

import dataclasses
import datetime
import json
import os
import pathlib
from typing import Sequence

from . import disk, ledger, slotlog

WORD = "LOG"
NO_PR = "no open PR fixes the ticket"
NO_WORKTREE = "no worktree was removed"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """One hand-back or clean-up.

    Attributes:
        kind: ``hand-back`` or ``clean-up``.
        time: when, in UTC (ISO).
        who: the worker (slot and agent) or the command.
        what: what returned or was freed.
        head: the PR head (the heads of the worktrees a clean removed).
    """

    kind: str
    time: str
    who: str
    what: str
    head: str


def beside(log: pathlib.Path, suffix: str) -> pathlib.Path:
    """A file of the log lines, beside the slot log.

    Args:
        log: the slot log.
        suffix: ``.events`` (one JSON object for each event) or ``.posted``
            (how many events were posted).

    Returns:
        The file.
    """
    return log.with_suffix(suffix)


def text(event: Event) -> str:
    """The line of an event.

    Args:
        event: the event.

    Returns:
        ``LOG <kind> <time> <who>: <what>; head <head>``.
    """
    return (
        f"{WORD} {event.kind} {event.time} {event.who}: {event.what}; head {event.head}"
    )


def hand_back(slot: ledger.Slot, head: str, now: datetime.datetime) -> Event:
    """The event of an agent that handed back and whose slot is freed.

    Args:
        slot: the slot as it was before it was freed.
        head: the head of the open PR that fixes the slot's ticket, or empty.
        now: the time now.

    Returns:
        The event: the task that returned, the slot and agent, and the head.
    """
    return Event(
        kind="hand-back",
        time=slotlog.utc(now).isoformat(),
        who=f"slot {slot.name} agent {slot.agent}",
        what=f"returned {slot.task}",
        head=head or NO_PR,
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Freed:
    """What a command that cleans freed.

    Attributes:
        who: the command.
        size: the bytes it freed.
        heads: the heads of the worktrees it removed.
    """

    who: str
    size: int
    heads: Sequence[str]


def record_clean(log: pathlib.Path, freed: Freed, now: datetime.datetime) -> None:
    """Record a clean-up that freed space; one that freed none is not recorded.

    Args:
        log: the slot log.
        freed: what it freed.
        now: the time now.
    """
    if freed.size:
        record(
            log,
            Event(
                kind="clean-up",
                time=slotlog.utc(now).isoformat(),
                who=freed.who,
                what=f"freed {disk.size_text(freed.size)}",
                head=", ".join(freed.heads) or NO_WORKTREE,
            ),
        )


def slurp(path: pathlib.Path) -> str:
    """The text of a file, empty when there is none.

    Args:
        path: the file.

    Returns:
        The text.
    """
    return path.read_text() if path.exists() else ""


def put(path: pathlib.Path, text: str) -> None:
    """Replace the text of a file, making its directory.

    Args:
        path: the file.
        text: what to write.
    """
    os.makedirs(path.parent, exist_ok=True)
    path.write_text(text)


def record(log: pathlib.Path, event: Event) -> None:
    """Add an event to the events file.

    Args:
        log: the slot log.
        event: the event.
    """
    path = beside(log, ".events")
    put(path, slurp(path) + json.dumps(dataclasses.asdict(event)) + "\n")


def read(log: pathlib.Path) -> Sequence[Event]:
    """Every recorded event.

    Args:
        log: the slot log.

    Returns:
        The events, oldest first; none when no file exists.
    """
    lines = slurp(beside(log, ".events")).splitlines()
    return [Event(**json.loads(each)) for each in lines]


def posted(log: pathlib.Path) -> int:
    """How many events were posted.

    Args:
        log: the slot log.

    Returns:
        The count; 0 when the file is missing or holds no number, so an event
        is said again rather than lost.
    """
    count = slurp(beside(log, ".posted"))
    return int(count) if count.isdigit() else 0


def post(log: pathlib.Path) -> None:
    """Print the ``LOG`` line of each event not yet posted, and mark them posted.

    Args:
        log: the slot log.
    """
    events = read(log)
    for each in events[posted(log) :]:
        print(text(each))
    put(beside(log, ".posted"), str(len(events)))

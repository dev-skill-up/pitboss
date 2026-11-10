"""The loop of ``slots watch`` (keyword: slots-watch, pitboss#415)."""

import argparse
import dataclasses
import datetime
import functools
import sys
import time
from typing import Callable, NoReturn, Sequence, TypeVar

from . import (
    agenttranscript,
    config,
    ledger,
    nextfound,
    processstart,
    slotlog,
    slotsheader,
    slotwatch,
    watchbeat,
)

Context = TypeVar("Context", bound=nextfound.Found)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Report:
    """What one round of the watcher found.

    Attributes:
        said: the lines of the round: what changed, ``OVERCAP``.
        free: whether a slot is free after it.
        free_line: makes the ``SLOT FREE`` line (it reads the queue).
        unmarked: the ``UNMARKED`` lines of the agents with no marker.
    """

    said: Sequence[str]
    free: bool
    free_line: Callable[[], str]
    unmarked: Sequence[str] = ()


def _refuse() -> NoReturn:
    print("slots watch needs [slots] agents-dir in the configuration", file=sys.stderr)
    raise SystemExit(2)


def _started(args: argparse.Namespace) -> datetime.datetime | None:
    given = getattr(args, "process_start", None)
    if given:
        return datetime.datetime.fromisoformat(given)
    return processstart.of_claude(args.safe_run)


def once(
    load: Callable[[], Context],
    free_line: Callable[[Context, ledger.Ledger, int], str],
    interval: int,
    lister: agenttranscript.Lister = agenttranscript.agent_files,
) -> Report:
    """One round: read the transcripts, write the ledger, beat.

    Args:
        load: reads the context afresh.
        free_line: makes the ``SLOT FREE`` line of a context, a ledger and a cap.
        interval: the seconds between rounds, for the heartbeat.
        lister: lists the transcript files of the tasks directory.

    Returns:
        What the round found.
    """
    found = load()
    slots = found.settings.slots
    if slots.watch.agents_dir is None:
        _refuse()
    started = _started(found.args)
    agents = agenttranscript.read_all(slots.watch.agents_dir, started, lister)
    made = slotwatch.read(ledger.configured(found.settings), agents, found.now, started)
    if made.changed:
        ledger.write(slots.ledger, made.book)
        entries = slotlog.changes(slotlog.read(slots.log), made.book, found.now)
        slotlog.append(slots.log, entries)
    watchbeat.beat(slots.ledger, found.now, interval)
    cap = len(slots.default) or len(made.book.slots)
    # the ledger is live now: the rows are the agents that run
    found.args.running = slotwatch.running(made.book)
    free = len(slotsheader.running(made.book)) < cap
    line = functools.partial(free_line, found, made.book, cap)
    return Report(said=made.said, free=free, free_line=line, unmarked=made.unmarked)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pace:
    """How fast the rounds go and how often a free slot is said again.

    Attributes:
        interval: the seconds between rounds.
        every: the rounds between two ``SLOT FREE`` lines.
        sleep: waits some seconds.
    """

    interval: int
    every: int = 1
    sleep: Callable[[float], None] = time.sleep


def pace_of(watched: config.Watch, given: int | None) -> Pace:
    """The pace of a watcher.

    Args:
        watched: its configuration.
        given: the ``--interval`` given, or None.

    Returns:
        The seconds between rounds (``poll-seconds`` unless given) and the rounds
        between two ``SLOT FREE`` lines (``remind-minutes``).
    """
    interval = watched.poll_seconds if given is None else given
    every = max(1, watched.remind_minutes * 60 // interval) if interval else 1
    return Pace(interval=interval, every=every)


def _round(one: Callable[[], Report]) -> Report:
    try:
        return one()
    except (OSError, ValueError) as error:
        print(f"WATCH FAILED: {error}", flush=True)
        raise SystemExit(1) from error


def loop(one: Callable[[], Report], pace: Pace, rounds: int) -> None:
    """Run rounds, printing their lines, with a wait between them.

    ``SLOT FREE`` is printed from the second round in a row with a free slot (the
    transcript of an agent launched a moment ago appears within one poll) and
    again every ``pace.every`` rounds until an agent fills the slot. An agent
    with no marker is said once.

    Args:
        one: makes a round.
        pace: the wait between rounds and the rounds between reminders.
        rounds: how many rounds, or 0 for no end.
    """
    count = 0
    run = 0
    told: set[str] = set()
    while not rounds or count < rounds:
        made = _round(one)
        for each in [*made.said, *(u for u in made.unmarked if u not in told)]:
            print(each, flush=True)
        told.update(made.unmarked)
        run = run + 1 if made.free else 0
        if run >= 2 and (run - 2) % pace.every == 0:
            print(made.free_line(), flush=True)
        count += 1
        if not rounds or count < rounds:
            pace.sleep(pace.interval)


def watch(
    args: argparse.Namespace,
    load: Callable[[argparse.Namespace], Context],
    free_line: Callable[[Context, ledger.Ledger, int], str],
) -> None:
    """Run ``slots watch``: rounds until ``--rounds`` of them are done.

    Args:
        args: the parsed arguments.
        load: reads the context of the arguments afresh.
        free_line: makes the ``SLOT FREE`` line.
    """
    pace = pace_of(load(args).settings.slots.watch, args.interval)

    def one() -> Report:
        return once(lambda: load(args), free_line, pace.interval)

    loop(one, pace, args.rounds)

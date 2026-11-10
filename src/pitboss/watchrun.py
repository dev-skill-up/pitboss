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
    """

    said: Sequence[str]
    free: bool
    free_line: Callable[[], str]


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
) -> Report:
    """One round: read the transcripts, write the ledger, beat.

    Args:
        load: reads the context afresh.
        free_line: makes the ``SLOT FREE`` line of a context, a ledger and a cap.
        interval: the seconds between rounds, for the heartbeat.

    Returns:
        What the round found.
    """
    found = load()
    slots = found.settings.slots
    if slots.watch.agents_dir is None:
        _refuse()
    started = _started(found.args)
    agents = agenttranscript.read_all(slots.watch.agents_dir, started)
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
    return Report(said=made.said, free=free, free_line=line)


def loop(one: Callable[[], Report], interval: int, rounds: int) -> None:
    """Run rounds, printing their lines, with a wait between them.

    ``SLOT FREE`` is printed from the second round in a row with a free slot: the
    transcript of an agent launched a moment ago appears within one poll.

    Args:
        one: makes a round.
        interval: the seconds between rounds.
        rounds: how many rounds, or 0 for no end.
    """
    count = 0
    before = False
    while not rounds or count < rounds:
        made = one()
        for each in made.said:
            print(each, flush=True)
        if made.free and before:
            print(made.free_line(), flush=True)
        before = made.free
        count += 1
        if not rounds or count < rounds:
            time.sleep(interval)


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

    def one() -> Report:
        return once(lambda: load(args), free_line, args.interval)

    loop(one, args.interval, args.rounds)

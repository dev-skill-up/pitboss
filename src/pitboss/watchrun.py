"""The loop of ``slots watch`` and its heartbeat (keyword: slots-watch, pitboss#415)."""

import argparse
import dataclasses
import datetime
import pathlib
import sys
import time
from typing import Callable, Sequence

from . import (
    watchbeat,
    agenttranscript,
    commands,
    configfile,
    ledger,
    nextlist,
    nextview,
    processstart,
    slotlog,
    slotsheader,
    slotwatch,
)
from .markers import Marker


def command(given: str, item: str) -> str:
    """The command that prints the brief of an item.

    Args:
        given: the configuration as the command was given it.
        item: the ticket or PR.

    Returns:
        The command.
    """
    return f"pitboss slots next {item} --config {given}"


def free_line(found: nextlist.Found, book: ledger.Ledger, cap: int) -> str:
    """The ``SLOT FREE`` line, naming the first startable item.

    Args:
        found: the context.
        book: the ledger.
        cap: the number of slots.

    Returns:
        The line.
    """
    view = nextlist.startable_view(found, commands.open_pulls(found), book)
    entries = slotlog.read(found.settings.slots.log)
    since = slotsheader.free_since(book, entries, found.now)
    free = cap - len(slotsheader.running(book))
    given = configfile.named(found.args)
    items = nextview.startable(view)
    if items:
        first = f"{items[0].reference} ({command(given, items[0].reference)})"
    elif view.ready:
        first = f"{view.ready[0]} ({command(given, '')})"
    else:
        first = "no open ticket or PR is queued: file the next ticket"
    return (
        f"{Marker.SLOT_FREE.text}: {free} of {cap} free since"
        f" {slotlog.utc(since).strftime(slotsheader.TIME_FORMAT)}; first startable:"
        f" {first}"
    )


Round = Callable[[bool], tuple[Sequence[str], bool]]


def loop(one: Round, interval: int, rounds: int) -> None:
    """Run rounds, printing their lines, with a wait between them.

    Args:
        one: a round: it is told whether the slot was free after the last one,
            and returns the lines to print and whether a slot is free now.
        interval: the seconds between rounds.
        rounds: how many rounds, or 0 for no end.
    """
    done = 0
    free = False
    while not rounds or done < rounds:
        lines, free = one(free)
        for line in lines:
            print(line, flush=True)
        done += 1
        if not rounds or done < rounds:
            time.sleep(interval)


def _started(args: argparse.Namespace) -> datetime.datetime | None:
    given = getattr(args, "process_start", None)
    if given:
        return datetime.datetime.fromisoformat(given)
    return processstart.of_claude(args.safe_run)


def once(
    args: argparse.Namespace, interval: int, free_before: bool
) -> tuple[Sequence[str], bool]:
    """One round: read the transcripts, write the ledger, say what changed.

    Args:
        args: the parsed arguments.
        interval: the seconds between rounds, for the heartbeat.
        free_before: whether the last round ended with a free slot.

    Returns:
        The lines (what changed, ``OVERCAP``, and ``SLOT FREE`` from the second
        round in a row with a free slot) and whether a slot is free now.
    """
    found = commands.load_context(args)
    slots = found.settings.slots
    root = slots.agents_dir
    if root is None:
        print(
            "slots watch needs [slots] agents-dir in the configuration", file=sys.stderr
        )
        raise SystemExit(2)
    started = _started(args)
    agents = agenttranscript.read_all(root, started)
    written = ledger.configured(found.settings)
    made = slotwatch.step(written, agents, found.now, started)
    if made.changed:
        ledger.write(slots.ledger, made.book)
        entries = slotlog.changes(slotlog.read(slots.log), made.book, found.now)
        slotlog.append(slots.log, entries)
    watchbeat.beat(slots.ledger, found.now, interval)
    cap = len(slots.default) or len(made.book.slots)
    free = len(slotsheader.running(made.book)) < cap
    if not (free and free_before):
        return made.lines, free
    names = slotwatch.running(made.book)
    live = dataclasses.replace(
        found, args=argparse.Namespace(**{**vars(args), "running": names})
    )
    return [*made.lines, free_line(live, made.book, cap)], free

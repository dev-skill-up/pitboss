"""The one path of a question of what is next (keyword: one-path).

``Mode -> read_world -> World -> decide -> Decisions -> projection -> render``:
``answer`` is the only caller of ``readworld.read_world``, so a command reads once,
and the commands that ask one question print the value of one projection of one
``Decisions``. After the lines, a decision a slot or an Opus agent takes gets its
brief, made as the briefs of ``suggest`` always were.
"""

import argparse
import functools
from typing import Iterable, Mapping, Sequence, assert_never

from . import (
    configfile,
    configloads,
    decide,
    ledger,
    mode,
    project,
    pullread,
    readworld,
    render,
    repoaccess,
    slotholding,
    slotlog,
    slotsheader,
    suggest,
    sweepline,
    work,
    workitem,
    world,
)
from .commands import Context
from .markers import Marker
from .queuereads import read_runner_runs

BRIEFED = frozenset({decide.Actor.WORKER, decide.Actor.REVIEWER, decide.Actor.RULING})


def reading_of(found: Context) -> readworld.Reading:
    """What the read of a command starts from.

    Args:
        found: the context.

    Returns:
        The reading: the ledger as the live agents make it, the holds, and where
        each repository's pull requests are read from.
    """
    settings = found.settings
    args = found.args
    book = slotholding.derived(
        ledger.configured(settings), getattr(args, "running", None)
    )
    runs = functools.partial(read_runner_runs, found)
    undraft = sweepline.undraft_check(found.github, settings, found.now, runs)
    owner = settings.project.repo.owner
    named, start = configfile.named(args), configfile.working_directory(args)
    return readworld.Reading(
        github=found.github,
        settings=settings,
        book=book,
        free=sum(1 for slot in book.slots if not slot.agent),
        holds=configloads.load_holds(named, start, owner),
        now=found.now,
        source=functools.partial(pullread.source_for, found.github, settings, undraft),
    )


def _extent(chosen: mode.Mode) -> readworld.Extent:
    match chosen:
        case mode.ItemNext():
            return readworld.Extent(named=[chosen.item], every_pull=False)
        case mode.WhatNext() | mode.FreeCheck() | mode.DispatchNext() | mode.Other():
            return readworld.Extent(named=[], every_pull=False)
        case _:  # pragma: no cover
            assert_never(chosen)


def decisions_of(found: Context, chosen: mode.Mode) -> decide.Decisions:
    """Read the world a mode asks for, once, and decide.

    Args:
        found: the context.
        chosen: the mode.

    Returns:
        The decisions.
    """
    return decide.decide(readworld.read_world(reading_of(found), _extent(chosen)))


def _pick(record: world.Record) -> suggest.Pick | None:
    match record:
        case world.PullRecord():
            facts = record.facts
            category = work.category_of(facts)
            listed = record.listed
            item = (
                workitem.Item(
                    category=category,
                    reference=listed.reference,
                    created_at=listed.created_at,
                    title=listed.title,
                )
                if category is not None
                else None
            )
            return suggest.Pick(
                reference=listed.reference,
                title=listed.title,
                category=category,
                item=item,
                pull=facts,
            )
        case world.TicketRecord():
            ticket = workitem.of_ticket(record.reference, record.issue, record.priority)
            return suggest.Pick(
                reference=record.reference,
                title=record.issue.title,
                category=ticket.category,
                item=ticket,
            )
        case world.Kept():
            return None
        case _:  # pragma: no cover
            assert_never(record)


def briefs(
    found: Context, decisions: decide.Decisions, chosen: Sequence[decide.Decision]
) -> Iterable[str]:
    """The briefs of the decisions a slot or an Opus agent takes, first five.

    Args:
        found: the context.
        decisions: the command's decisions (their records).
        chosen: the decisions printed, in order.

    Returns:
        The lines of ``suggest``: the file of each brief, then each brief.
    """
    briefed = [each for each in chosen if each.actor in BRIEFED][: suggest.TOP]
    records = [decisions.records[each.item] for each in briefed]
    picks = [pick for pick in map(_pick, records) if pick is not None]
    facts = [each.facts for each in records if isinstance(each, world.PullRecord)]
    items = [pick.item for pick in picks if pick.item is not None]
    failed = ledger.configured(found.settings).failed
    source = suggest.sourced(found, facts, items, failed)
    made = [suggest.suggest(source, pick) for pick in picks]
    saved = [suggest.dispatched(source, each) for each in made]
    return [*saved, *suggest.ranked(made, 1, len(made))]


def _printed(answer: decide.Answer) -> Sequence[decide.Decision]:
    match answer:
        case decide.Work():
            return [answer.first, *answer.rest]
        case decide.NotEnoughWork():
            return []


def _item_printed(
    given: project.ItemAnswer,
) -> Sequence[decide.Decision]:
    match given:
        case project.ItemDecided():
            return [given.decision]
        case decide.Work() | decide.NotEnoughWork():
            return _printed(given)


def answer(found: Context, chosen: mode.Mode) -> None:
    """Answer a question of what is next, and print the briefs of its decisions.

    Args:
        found: the context.
        chosen: the mode: what is next, for an item, or for a free slot.
    """
    decisions = decisions_of(found, chosen)
    match chosen:
        case mode.WhatNext() | mode.FreeCheck():
            listed = project.what_next(decisions)
            lines = [*render.answer(listed)]
            shown = _printed(listed)
        case mode.ItemNext():
            asked = project.item_next(decisions, chosen.item)
            lines = [*render.item(asked)]
            shown = _item_printed(asked)
        case mode.DispatchNext() | mode.Other():
            lines, shown = [], []
        case _:  # pragma: no cover
            assert_never(chosen)
    for line in [*lines, *briefs(found, decisions, shown)]:
        print(line)
    repoaccess.finish(found.access)


def dispatch(found: Context, chosen: mode.DispatchNext) -> project.DispatchAnswer:
    """The one next piece of work, for ``act dispatch-next``.

    Args:
        found: the context.
        chosen: the mode.

    Returns:
        The head of the order, or why the named item is not it.
    """
    return project.dispatch_next(decisions_of(found, chosen), chosen.want)


def mode_of(args: argparse.Namespace, found: Context, options: Mapping[str, str]) -> mode.Mode:
    """The mode of a command line, read with the project of its configuration.

    Args:
        args: the parsed arguments.
        found: the context.
        options: an ``act`` command's options.

    Returns:
        The mode.
    """
    return mode.parse(args, found.settings.project.repo, options)


def first_line(found: Context) -> str:
    """The first decision of what is next (``IDLE SLOT``, ``SLOT FREE``, refill).

    Args:
        found: the context.

    Returns:
        Its line, or the ``NOT ENOUGH WORK`` line.
    """
    asked = mode.WhatNext(command="slots next")
    return render.first(project.what_next(decisions_of(found, asked)))


def refill_line(found: Context, name: str) -> str:
    """What an emptied slot takes next (``slots free`` prints it).

    Args:
        found: the context.
        name: the slot.

    Returns:
        ``SLOT <name> NEXT: <the first decision>``.
    """
    return f"SLOT {name} NEXT: {first_line(found)}"


def free_line(found: Context, book: ledger.Ledger, cap: int) -> str:
    """The ``SLOT FREE`` line of ``slots watch``, naming the first decision.

    Args:
        found: the context.
        book: the ledger.
        cap: the number of slots.

    Returns:
        The line.
    """
    since = slotsheader.free_since(book, found.settings.slots.log, found.now)
    free = cap - len(slotsheader.running(book))
    return (
        f"{Marker.WATCH_SLOT_FREE.text}: {free} of {cap} free since"
        f" {slotlog.utc(since).strftime(slotsheader.TIME_FORMAT)}; first startable:"
        f" {first_line(found)}"
    )

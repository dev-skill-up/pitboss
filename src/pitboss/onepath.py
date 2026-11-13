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
    answer,
    blockedby,
    configfile,
    configloads,
    decide,
    finishpartial,
    ledger,
    mode,
    nextfound,
    project,
    pullread,
    pulls,
    readworld,
    render,
    sharedred,
    slotholding,
    slotlog,
    slotsheader,
    suggest,
    sweepline,
    work,
    workitem,
    world,
)
from .markers import Marker
from .queuereads import read_runner_runs

BRIEFED = frozenset({answer.Actor.WORKER, answer.Actor.REVIEWER, answer.Actor.RULING})


def _settled(found: nextfound.Found, facts: pulls.PullFacts) -> pulls.PullFacts:
    # the settlers, on one pull request: blockers, shared red, hand-back
    blocked = blockedby.settle(found.github, [facts])[0]
    shared = sharedred.settle(found.github, blocked)[0]
    return pulls.readable(finishpartial.settle(shared)[0])[0]


def reading_of(found: nextfound.Found) -> readworld.Reading:
    """What the read of a command starts from.

    Args:
        found: the context.

    Returns:
        The reading: the ledger as the live agents make it, the holds, where
        each repository's pull requests are read from, the settlers, the decider.
    """
    settings, args = found.settings, found.args
    book = slotholding.derived(
        ledger.configured(settings), getattr(args, "running", None)
    )
    runs = functools.partial(read_runner_runs, found)
    undraft = sweepline.undraft_check(found.github, settings, found.now, runs)
    named, start = configfile.named(args), configfile.working_directory(args)
    return readworld.Reading(
        github=found.github,
        settings=settings,
        book=book,
        free=sum(1 for slot in book.slots if not slot.agent),
        holds=configloads.load_holds(named, start, settings.project.repo.owner),
        now=found.now,
        source=functools.partial(pullread.source_for, found.github, settings, undraft),
        settle=functools.partial(_settled, found),
        decide_item=decide.decide_item,
    )


def _extent(chosen: mode.Mode) -> readworld.Extent:
    match chosen:
        case mode.ItemNext():
            return readworld.Extent(named=[chosen.item], every_pull=False)
        case mode.WhatNext() | mode.DispatchNext() | mode.Other():
            return readworld.Extent(named=[], every_pull=False)
        case _:  # pragma: no cover
            assert_never(chosen)


def judged(found: nextfound.Found, chosen: mode.Mode) -> decide.Judgement:
    """Read the world a mode asks for, once, and decide.

    Args:
        found: the context.
        chosen: the mode.

    Returns:
        The decisions, with their records.
    """
    return decide.decide(readworld.read_world(reading_of(found), _extent(chosen)))


def _pull_pick(record: world.PullRecord) -> suggest.Pick:
    row, category = record.row, work.category_of(record.facts)
    item = None
    if category is not None:
        item = workitem.Item(
            category=category,
            reference=row.reference,
            created_at=row.created_at,
            title=row.title,
        )
    return suggest.Pick(
        reference=row.reference,
        title=row.title,
        category=category,
        item=item,
        pull=record.facts,
    )


def _ticket_pick(record: world.TicketRecord) -> suggest.Pick:
    ticket = workitem.of_ticket(record.reference, record.issue, record.priority)
    return suggest.Pick(
        reference=record.reference,
        title=record.issue.title,
        category=ticket.category,
        item=ticket,
    )


def _pick(record: world.Record) -> suggest.Pick | None:
    match record:
        case world.PullRecord():
            return _pull_pick(record)
        case world.TicketRecord():
            return _ticket_pick(record)
        case world.Kept():
            return None
        case _:  # pragma: no cover
            assert_never(record)


def briefs(
    found: nextfound.Found,
    records: Mapping[str, world.Record],
    chosen: Sequence[answer.Decision],
) -> Iterable[str]:
    """The briefs of the decisions a slot or an Opus agent takes.

    Args:
        found: the context.
        records: the record of each decided item.
        chosen: the decisions printed, in order.

    Returns:
        The lines of ``suggest``: the file of each brief, then each brief.
    """
    taken = [records[each.item] for each in chosen if each.actor in BRIEFED]
    picks = [pick for pick in map(_pick, taken) if pick is not None]
    facts = [each.facts for each in taken if isinstance(each, world.PullRecord)]
    items = [pick.item for pick in picks if pick.item is not None]
    failed = ledger.configured(found.settings).failed
    return suggest.lines(suggest.sourced(found, facts, items, failed), picks)


def _printed(given: project.ItemAnswer) -> Sequence[answer.Decision]:
    match given:
        case answer.Decision():
            return [given]
        case answer.Work():
            return render.every(given)
        case answer.NotEnoughWork():
            return []


def _said(
    chosen: mode.Mode, decided: answer.Decided
) -> tuple[Sequence[str], Sequence[answer.Decision]]:
    match chosen:
        case mode.WhatNext():
            listed = project.what_next(decided)
            return render.answer_lines(listed), _printed(listed)
        case mode.ItemNext():
            asked = project.item_next(decided, chosen.item)
            return render.item(asked), _printed(asked)
        case mode.DispatchNext() | mode.Other():
            return [], []
        case _:  # pragma: no cover
            assert_never(chosen)


def answer_of(found: nextfound.Found, chosen: mode.Mode) -> None:
    """Answer a question of what is next, and print the briefs of its decisions.

    Args:
        found: the context.
        chosen: the mode: what is next, for an item, or for a free slot.
    """
    judgement = judged(found, chosen)
    lines, shown = _said(chosen, judgement.decided)
    for text in [*lines, *briefs(found, judgement.records, shown)]:
        print(text)


def dispatch(
    found: nextfound.Found, chosen: mode.DispatchNext
) -> answer.DispatchAnswer:
    """The one next piece of work, for ``act dispatch-next``.

    Args:
        found: the context.
        chosen: the mode.

    Returns:
        The head of the order, or why the named item is not it.
    """
    return project.dispatch_next(judged(found, chosen).decided, chosen.want)


def mode_of(
    args: argparse.Namespace, found: nextfound.Found, options: Mapping[str, str]
) -> mode.Mode:
    """The mode of a command line, read with the project of its configuration.

    Args:
        args: the parsed arguments.
        found: the context.
        options: an ``act`` command's options.

    Returns:
        The mode.
    """
    return mode.parse(args, found.settings.project.repo, options)


def first_line(found: nextfound.Found) -> str:
    """The first decision of what is next (``IDLE SLOT``, ``SLOT FREE``, refill).

    Args:
        found: the context.

    Returns:
        Its line, or the ``NOT ENOUGH WORK`` line.
    """
    asked = mode.WhatNext(asked=mode.Asked.SLOTS_NEXT)
    return render.first(project.what_next(judged(found, asked).decided))


def refill_line(found: nextfound.Found, name: str) -> str:
    """What an emptied slot takes next (``slots free`` prints it).

    Args:
        found: the context.
        name: the slot.

    Returns:
        ``SLOT <name> NEXT: <the first decision>``.
    """
    return f"SLOT {name} NEXT: {first_line(found)}"


def free_line(found: nextfound.Found, book: ledger.Ledger, cap: int) -> str:
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

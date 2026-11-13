"""The one path of a question of what is next (keyword: one-path).

``Mode -> read_world -> World -> decide -> Decisions -> projection -> render``:
``answer`` is the only caller of ``readworld.read_world``, so a command reads once,
and the commands that ask one question print the value of one projection of one
``Decisions``. After the lines, a decision a slot or an Opus agent takes gets its
brief, made as the briefs of ``suggest`` always were.
"""

import argparse
import dataclasses
import functools
from typing import Callable, Mapping, Sequence, assert_never

from . import (
    agentstarts,
    answer,
    blockedby,
    concurrently,
    configfile,
    configloads,
    decide,
    finishpartial,
    gateread,
    handedback,
    holdconfig,
    ledger,
    listed,
    logline,
    mode,
    nextfound,
    project,
    pullread,
    pulls,
    sharedred,
    quiesce,
    readworld,
    render,
    slotholding,
    suggest,
    sweepline,
    ticketnotes,
    timing,
    work,
    workitem,
    world,
)
from .queuereads import read_runner_runs

# how a run reads a listing row: the pull request, settled by its blockers
PullReader = Callable[[listed.Listed], pulls.Read]


def _holds(found: nextfound.Found) -> holdconfig.Holds:
    # the owner's holds on new pull requests, from the configuration's own file
    args = found.args
    named, start = configfile.named(args), configfile.working_directory(args)
    return configloads.load_holds(named, start, found.settings.project.repo.owner)


def _book(found: nextfound.Found) -> ledger.Ledger:
    # the ledger as the live agents make it
    running = getattr(found.args, "running", None)
    return slotholding.derived(ledger.configured(found.settings), running)


def _reader(found: nextfound.Found, undraft: Callable[[], bool]) -> PullReader:
    # a run reads a pull request once, settled by its blockers: a pull request
    # read as a shared red's closure is not read again when it is examined
    done: dict[str, pulls.Read] = {}

    def read(row: listed.Listed) -> pulls.Read:
        if row.reference not in done:
            github, settings = found.github, found.settings
            source = pullread.source_for(github, settings, undraft, row.repo)
            facts = pulls.fetch(source, row.repo, row.number)
            done[row.reference] = blockedby.settle(github, [facts])[0]
        return done[row.reference]

    return read


def _settled(
    found: nextfound.Found,
    read: PullReader,
    row: listed.Listed,
    others: Sequence[listed.Listed],
) -> pulls.PullFacts:
    # its shared red reads the repository's other open pull requests only when red
    siblings = functools.partial(concurrently.each, read, others)
    shared = sharedred.settle_one(found.github, read(row), siblings)
    return pulls.readable(finishpartial.settle([shared])[0])[0]


def reading_of(found: nextfound.Found, measured: sweepline.Look) -> readworld.Reading:
    """What the read of a command starts from.

    Args:
        found: the context.
        measured: the run's one look at the runners.

    Returns:
        The reading: the ledger as the live agents make it, the holds, how a
        pull request is read and settled, the decider, the hand-backs.
    """
    settings = found.settings
    undraft = functools.partial(sweepline.clear, measured, settings.runners)
    read = _reader(found, undraft)
    return readworld.Reading(
        github=found.github,
        settings=settings,
        book=_book(found),
        holds=_holds(found),
        now=found.now,
        pull=functools.partial(_settled, found, read),
        decide_item=decide.decide_item,
        gated=gateread.reader(found.github),
        quiesced=quiesce.is_on(settings.slots.ledger),
        released=functools.partial(handedback.ledger_after_hand_backs, found),
    )


def _extent(chosen: mode.Mode) -> readworld.Extent:
    match chosen:
        case mode.ItemNext():
            return readworld.Extent(named=[chosen.item], every_pull=False)
        case mode.Sweep():
            return readworld.Extent(named=[], every_pull=True)
        case mode.WhatNext() | mode.DispatchNext() | mode.Other():
            return readworld.Extent(named=[], every_pull=False)
        case _:  # pragma: no cover
            assert_never(chosen)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """The world a command read, and what it decides.

    Attributes:
        made: the world.
        judgement: its decisions, with their records.
        runners: the run's one look at the runners, which the read asked too.
    """

    made: world.World
    judgement: decide.Judgement
    runners: sweepline.Look

    @property
    def decided(self) -> answer.Decided:
        """The decisions of the world.

        Returns:
            Every decision, and what is next.
        """
        return self.judgement.decided


def looked(found: nextfound.Found, chosen: mode.Mode) -> Seen:
    """Read the world a mode asks for, once, and decide: the one read (P6).

    Args:
        found: the context.
        chosen: the mode.

    Returns:
        The world and its decisions.
    """
    runs = functools.partial(read_runner_runs, found)
    measured = sweepline.runners_look(
        found.github, runs, found.settings.runners, found.now
    )
    made = readworld.read_world(reading_of(found, measured), _extent(chosen))
    return Seen(made=made, judgement=decide.decide(made), runners=measured)


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


def pick(record: world.Record) -> suggest.Pick | None:
    """What a slot takes for an item's record: its work item, or its PR.

    Args:
        record: the record.

    Returns:
        The pick, None for an item the read kept.
    """
    match record:
        case world.PullRecord():
            return _pull_pick(record)
        case world.TicketRecord():
            return _ticket_pick(record)
        case world.Kept():
            return None
        case _:  # pragma: no cover
            assert_never(record)


def briefed(
    found: nextfound.Found,
    records: Mapping[str, world.Record],
    chosen: Sequence[answer.Decision],
) -> tuple[suggest.Source, Sequence[suggest.Pick]]:
    """What the briefs of the decisions a slot or an Opus agent takes are made from.

    Args:
        found: the context.
        records: the record of each decided item.
        chosen: the decisions printed, in order.

    Returns:
        The source, with the volume read, and the picks.
    """
    taken = [records[each.item] for each in chosen if agentstarts.starts(each, records)]
    picks = [pick for pick in map(pick, taken) if pick is not None]
    facts = [each.facts for each in taken if isinstance(each, world.PullRecord)]
    items = [pick.item for pick in picks if pick.item is not None]
    failed = ledger.configured(found.settings).failed
    got = suggest.with_volume(found, suggest.sourced(found, facts, items, failed))
    return got, picks


def _printed(given: project.ItemAnswer) -> Sequence[answer.Decision]:
    match given:
        case answer.Decision():
            return [given]
        case answer.Work():
            return render.every(given)
    return []  # NotEnoughWork


def answered(
    chosen: mode.Mode, decided: answer.Decided
) -> tuple[Sequence[str], Sequence[answer.Decision]]:
    """What a question of what is next prints, and the decisions it prints.

    Args:
        chosen: the mode; only ``next`` and ``next <item>`` print an answer.
        decided: the decisions of the world.

    Returns:
        The lines, and the decisions they name, in order.
    """
    match chosen:
        case mode.WhatNext():
            listed = project.what_next(decided)
            return render.answer_lines(listed), _printed(listed)
        case mode.ItemNext():
            asked = project.item_next(decided, chosen.item)
            return render.item(asked), _printed(asked)
        case mode.DispatchNext() | mode.Sweep() | mode.Other():
            return [], []
        case _:  # pragma: no cover
            assert_never(chosen)


def seen_for(found: nextfound.Found) -> Seen:
    """The one read of a command, with the mode of its own command line.

    Args:
        found: the context.

    Returns:
        The world and its decisions.
    """
    return looked(found, mode_of(found.args, found, {}))


def answer_of(found: nextfound.Found) -> None:
    """Answer a question of what is next, and print the briefs of its decisions.

    Args:
        found: the context; its command line says the mode.
    """
    chosen = mode_of(found.args, found, {})
    judgement = looked(found, chosen).judgement
    timing.note(found.args, "world read and decided", len(judgement.records), "items")
    lines, shown = answered(chosen, judgement.decided)
    lines = [*ticketnotes.asked(found.args, chosen, judgement.records), *lines]
    source, picks = briefed(found, judgement.records, shown)
    tail = suggest.tail(source) if isinstance(chosen, mode.WhatNext) else []
    said = [*lines, *tail, *suggest.lines(source, picks)]
    logline.after(said, found.settings.slots.log)
    timing.note(found.args, "lists and briefs printed", len(picks), "briefs")


def _item_read(found: nextfound.Found, item: str) -> Seen:
    # the one read with one item named, as ``next <item>`` reads it
    return looked(found, mode.ItemNext(asked=mode.Asked.NEXT, item=item))


def pull_records(found: nextfound.Found, item: str) -> Sequence[world.PullRecord]:
    """The record of one open pull request, read as ``next <item>`` reads it.

    Args:
        found: the context.
        item: ``owner/name#number``.

    Returns:
        Its record; none when it is no open pull request of the configuration.
    """
    made = _item_read(found, item).made
    return [each for each in world.pull_records(made) if each.row.reference == item]


def dispatch(found: nextfound.Found, chosen: mode.DispatchNext) -> answer.Decided:
    """The decisions ``act dispatch-next`` looks the head of the order up in.

    Args:
        found: the context.
        chosen: the mode.

    Returns:
        The decisions of the world.
    """
    return looked(found, chosen).decided


def decided_for(found: nextfound.Found, item: str) -> answer.Decided:
    """What ``act`` looks a verb up in: the item's decision (keyword: gate, P8).

    The world is read with the item named, as ``next <item>`` reads it, so the
    verb runs only when the advice for the item is that verb.

    Args:
        found: the context.
        item: ``owner/name#number``.

    Returns:
        The decisions of the world read with the item named.
    """
    return _item_read(found, item).decided


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


def first_of(seen: Seen) -> str:
    """The first decision of what is next, of a world already read.

    Args:
        seen: the command's one read and its decisions.

    Returns:
        Its line, or the ``NOT ENOUGH WORK`` line.
    """
    return render.first(project.what_next(seen.judgement.decided))


def first_line(found: nextfound.Found) -> str:
    """The first decision of what is next (``IDLE SLOT``, ``SLOT FREE``).

    Args:
        found: the context.

    Returns:
        Its line, or the ``NOT ENOUGH WORK`` line.
    """
    return first_of(seen_for(found))

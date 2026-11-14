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
    answer,
    config,
    configfile,
    configloads,
    decide,
    examine,
    gateread,
    gates,
    handedback,
    holdconfig,
    ledger,
    listed,
    logline,
    mode,
    modeextent,
    modequestion,
    nextfound,
    project,
    pullread,
    pulls,
    quiesce,
    readworld,
    render,
    sharedred,
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

PullReader = readworld.PullReader  # the pull request as read, once a run


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
    # a run reads a pull request once: a pull request read as a shared red's
    # closure is not read again when it is examined
    done: dict[str, pulls.PullRead] = {}
    gated: dict[str, config.Config] = {}  # a repository's gate, read once

    def read(row: listed.Listed) -> pulls.PullRead:
        if row.reference not in done:
            github, slug = found.github, row.repo.slug
            if slug not in gated:
                gated[slug] = gates.settled(github, found.settings, {slug})
            source = pullread.source_for(github, gated[slug], undraft, row.repo)
            done[row.reference] = pulls.fetch(source, row.repo, row.number)
        return done[row.reference]

    return read


def _closures(found: nextfound.Found, read: PullReader) -> world.Closures:
    # the gate and the shared red of a pull request, read as its closure
    shared = functools.partial(sharedred.holders_closure, found.github, read)
    return world.Closures(gated=gateread.reader(found.github), shared=shared)


def _examiner(found: nextfound.Found, read: PullReader) -> readworld.Examiner:
    # how the walk reads an item it reaches (``examine``)
    context = examine.Context(
        github=found.github,
        settings=found.settings,
        now=found.now,
        pull=read,
        closures=_closures(found, read),
    )
    return readworld.Examiner(
        pull=functools.partial(examine.examine_pull, context),
        ticket=functools.partial(examine.examine_ticket, context),
    )


def reading_of(
    found: nextfound.Found, measured: sweepline.Look, acts: readworld.Acts
) -> readworld.Reading:
    """What the read of a command starts from.

    Args:
        found: the context.
        measured: the run's one look at the runners.
        acts: what the act verb asked for is decided from, read (``actread``).

    Returns:
        The reading: the ledger, the holds, the examiner, the decider.
    """
    settings = found.settings
    undraft = functools.partial(sweepline.clear, measured, settings.runners)
    examiner = _examiner(found, _reader(found, undraft))
    return readworld.Reading(
        github=found.github,
        settings=settings,
        book=_book(found),
        holds=_holds(found),
        judge=JUDGE,
        examiner=examiner,
        quiesced=quiesce.is_on(settings.slots.ledger),
        released=functools.partial(handedback.ledger_after_hand_backs, found),
        acts=acts,
    )


JUDGE = readworld.Judge(
    decides=decide.decide_in,
    pull_kept=decide.pull_kept,
    ticket_kept=decide.ticket_kept,
)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Seen:
    """The world a command read, and what it decides.

    Attributes:
        made: the world as read (``decide.facts_of`` gives a pull request's step).
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


def looked(
    found: nextfound.Found, chosen: mode.Mode, acts: readworld.Acts = readworld.no_acts
) -> Seen:
    """Read the world a mode asks for, once, and decide: the one read (P6).

    Args:
        found: the context.
        chosen: the mode.
        acts: what an ``act`` verb is decided from, read (``actread``).

    Returns:
        The world and its decisions.
    """
    runs = functools.partial(read_runner_runs, found)
    measured = sweepline.runners_look(
        found.github, runs, found.settings.runners, found.now
    )
    made = readworld.read_world(
        reading_of(found, measured, acts), modeextent.extent_of(chosen)
    )
    judged = decide.decide(made)
    return Seen(made=made, judgement=judged, runners=measured)


def _pull_pick(record: world.PullRecord) -> suggest.Pick:
    facts = decide.facts_of(record)
    row, category = record.row, work.category_of(facts)
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
        pull=facts,
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
        case world.Occupied():
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
    taken = [records[each.item] for each in chosen if decide.starts(each, records)]
    picks = [pick for pick in map(pick, taken) if pick is not None]
    pulled = [each for each in taken if isinstance(each, world.PullRecord)]
    facts = [decide.facts_of(each) for each in pulled]
    items = [pick.item for pick in picks if pick.item is not None]
    failed = ledger.configured(found.settings).failed
    got = suggest.with_volume(found, suggest.sourced(found, facts, items, failed))
    # keyword: org-search: the gates of the briefed items' repositories, no other
    slugs = {pick.reference.rpartition("#")[0] for pick in picks}
    gated = gates.settled(found.github, got.settings, slugs)
    return dataclasses.replace(got, settings=gated), picks


def _printed(given: project.ItemAnswer) -> Sequence[answer.Decision]:
    match given:
        case answer.Decision():
            return [given]
        case answer.Work():
            return render.every(given)
    return []  # NotEnoughWork


def _listed(listed: answer.Answer) -> tuple[Sequence[str], Sequence[answer.Decision]]:
    return render.answer_lines(listed), _printed(listed)


def _asked(
    asked: project.ItemAnswer,
) -> tuple[Sequence[str], Sequence[answer.Decision]]:
    return render.item(asked), _printed(asked)


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
    answers = mode.question_of(chosen).answers
    match answers:
        case modequestion.Answers.LIST:
            return _listed(project.what_next(decided))
        case modequestion.Answers.ITEM:
            return _asked(project.item_next(decided, mode.item_of(chosen)))
        case modequestion.Answers.NOTHING:
            return [], []
        case _:  # pragma: no cover
            assert_never(answers)


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
    listing = mode.question_of(chosen).answers is modequestion.Answers.LIST
    tail = suggest.tail(source) if listing else []
    said = [*lines, *tail, *suggest.lines(source, picks)]
    logline.after(said, found.settings.slots.log)
    timing.note(found.args, "lists and briefs printed", len(picks), "briefs")


def pull_records(found: nextfound.Found) -> Sequence[world.PullRecord]:
    """The records of the pull requests the mode of the command line names.

    ``pins-review <item>`` names its item and ``push --mechanical`` the branches it
    pushes; each is read as ``next <item>`` reads an item (keyword: one-path).

    Args:
        found: the context; its command line says the mode.

    Returns:
        The records of the open pull requests the mode names.
    """
    return world.named_pulls(seen_for(found).made)


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

"""The commands: thin wrappers that read, decide with the other modules, and print.

Reads go through ``args.safe_run``; changes through ``args.run``, which is
a dry run unless ``--no-dry-run`` is given.
"""

import argparse
import dataclasses
import datetime
import functools
import logging
import os
import pathlib
from typing import AbstractSet, Mapping, Sequence

from . import (
    account,
    autoclean,
    cleanconfig,
    cleanjob,
    concurrently,
    config,
    configfile,
    dead,
    draftmoves,
    gates,
    ghapi,
    ghmemo,
    headchecks,
    ledger,
    ledgerowner,
    localsections,
    offering,
    machine as machines,
    pullmarks,
    pulls,
    queue,
    readyline,
    removedline,
    repoaccess,
    report,
    scratch,
    summaryline,
    scratchconfig,
    shapes,
    slotholding,
    slotreport,
    sweepline,
    syncguard,
    syncing,
    tasklist,
    timing,
    blockedby,
    finishpartial,
    sharedred,
    workerlines,
    workhours,
)
from . import diskline, pulllines, pullstate, unlabeled, unledgered, unreadableline
from .failures import describe, read_all
from .running import KeywordRun
from .queuereads import read_queue_runs, read_runner_runs, runner_runs


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Context:
    """What every command starts from.

    Attributes:
        settings: the configuration, with the owner's other repositories.
        access: what could not be read (``repoaccess.finish`` says it).
        clean: what ``clean-container`` looks at and keeps.
        scratch: the scratch repositories (``[scratch]``).
        github: the API.
        now: the time now.
        args: the parsed arguments.
        stands: the PRs whose ticket waits for an open blocker (blocked-pull).
    """

    settings: config.Config
    access: repoaccess.Access
    clean: cleanconfig.Clean
    scratch: scratchconfig.Scratch
    github: ghapi.GitHub
    now: datetime.datetime
    args: argparse.Namespace
    stands: pullmarks.Stands = dataclasses.field(default_factory=dict)


working_directory = configfile.working_directory


def running_in(args: argparse.Namespace) -> AbstractSet[pathlib.Path]:
    """The directories a command runs in, which no removal may take.

    ``PWD`` (the shell's) and the process's own: a sweep or a cleaning keeps a
    path that is or holds either (keyword: clean-worktrees).

    Args:
        args: the parsed arguments.

    Returns:
        The directories.
    """
    return frozenset({working_directory(args), pathlib.Path(os.getcwd())})


def load_settings(args: argparse.Namespace) -> config.Config:
    """Load the configuration the command was given.

    Args:
        args: the parsed arguments.

    Returns:
        The configuration.
    """
    return configfile.load(configfile.named(args), working_directory(args))


def open_pulls(found: Context) -> Sequence[pulls.Read]:
    """Read every open PR the configuration names, and record the look at the runners.

    Args:
        found: the context.

    Returns:
        The PRs, a PR whose API call failed as an ``Unreadable``.
    """
    runs = functools.partial(read_runner_runs, found)
    read = sweepline.looked_pulls(found.github, found.settings, found.now, runs)
    read = _waiting(found.github, read)[0]
    timing.note(found.args, "open pull requests read", len(read), "pull requests")
    return read


def _waiting(
    github: ghapi.GitHub, read: Sequence[pulls.Read]
) -> tuple[Sequence[pulls.Read], Sequence[str]]:
    # keywords: blocked-by, shared-red: a declared blocker first, then a shared red
    blocked, said = blockedby.settle(github, read)
    settled, shared = sharedred.settle(github, blocked)
    finished, partial = finishpartial.settle(settled)  # keyword: finish-partial
    lines = [*said.values(), *sharedred.lines(shared).values(), *partial]
    return finished, [*lines, *finishpartial.stranded(finished)]


def whole_order(found: Context) -> Context:
    """The context with every repository's gate, which the whole order needs.

    Args:
        found: the context, with the gate of the item's repository alone.

    Returns:
        The context with every repository's gate read.
    """
    every = gates.settled(found.github, found.settings)
    return dataclasses.replace(found, settings=every)


def _reading(args: argparse.Namespace) -> KeywordRun:
    # keyword: read-memo (pitboss#453): what `slots next` reads, it reads once
    if getattr(args, "action", None) == "next":
        return ghmemo.memoized(args.safe_run)
    return args.safe_run  # type: ignore[no-any-return]


def load_context(args: argparse.Namespace) -> Context:
    """Load the configuration and set up the API.

    Args:
        args: the parsed arguments.

    Returns:
        The context.
    """
    logging.getLogger("commander_data.run").setLevel(logging.WARNING)
    now = timing.current_time(args)
    github = ghapi.GitHub(run=_reading(args), mutate=args.run)
    start = working_directory(args)
    given = configfile.named(args)
    access = repoaccess.read(
        github, given, start, functools.partial(repoaccess.item_gates, args)
    )
    owner = access.settings.project.repo.owner
    timing.note(args, "context and configuration read")
    return Context(
        settings=access.settings,
        access=access,
        clean=configfile.load_clean(given, start),
        scratch=configfile.load_scratch(given, start, owner),
        github=github,
        now=now,
        args=args,
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Detail:
    """What the sweep reads of one PR beyond its facts.

    Attributes:
        pull: the PR.
        failures: each failed check's id and what was read of it.
        said: what is said of the PR's removal from the merge queue.
        moves: what is said of a draft-state change that was not the sweep's.
    """

    pull: pulls.PullFacts
    failures: Mapping[int, shapes.Failure]
    said: removedline.Said
    moves: Sequence[str]


def _detail(
    found: Context, runs: Sequence[queue.QueueRun], pull: pulls.Read
) -> Detail | shapes.Unreadable:
    if isinstance(pull, shapes.Unreadable):
        return pull
    return Detail(
        pull=pull,
        failures=read_all(found.github, pull),
        said=removedline.tell(found.github, found.settings, pull, runs),
        moves=draftmoves.tell(found.github, pull.repo.slug, pull.pull.number),
    )


def _pull_lines(
    found: Context, newest: Mapping[str, queue.QueueRun], got: Detail
) -> bool:
    pull = got.pull
    print(report.pull_line(pull, newest), flush=True)
    if pullmarks.say_blocked(found.stands, pull):
        return False
    latest = newest.get(pulls.reference(pull))
    queued = latest is not None and not latest.run.finished
    why = {check_id: describe(each) for check_id, each in got.failures.items()}
    steps = {check_id: each.steps for check_id, each in got.failures.items()}
    shown = pulllines.lines(pull, found.now, found.settings, steps, got.failures)
    acts = report.action_lines(pull, found.settings, queued, why)
    blocked = pullstate.blocked_lines(found.github, found.settings, pull, ())
    for line in (*shown, *got.moves, *removedline.settle(got.said, acts), *blocked):
        print(line)
    return pulls.conflicted(pull) or bool(
        headchecks.unanswered(pull.checks, pull.signals)
    )


def _pull_section(
    found: Context, runs: Sequence[queue.QueueRun], read: Sequence[pulls.Read]
) -> bool:
    newest = queue.newest_by_reference(runs)
    broken = False
    for got in concurrently.as_ready(lambda pull: _detail(found, runs, pull), read):
        if isinstance(got, shapes.Unreadable):
            print(unreadableline.unreadable_line(got))
        else:
            broken = _pull_lines(found, newest, got) or broken
    return broken


def sweep_look(found: Context) -> dead.Look:
    """What looking at the checkouts needs, from the context.

    Args:
        found: the context.

    Returns:
        The look.
    """
    return dead.Look(
        run=found.args.safe_run,
        github=found.github,
        settings=found.settings,
        clean=found.clean,
        working=running_in(found.args),
        marker_expiry=workhours.expiry_of(found.now),
    )


def _clean_section(found: Context) -> account.Report:
    # A sweep that removes: safe_run really runs (keyword: auto-clean).
    listed = found.clean.worktrees is cleanconfig.Worktrees.LIST
    option = cleanjob.Option(run=found.args.safe_run, dry=False, list_only=listed)
    look = sweep_look(found)
    machine = machines.real_machine(
        found.args.env, found.now, running_in(found.args), found.args.usage
    )
    done = autoclean.clean_report(look, machine, option)
    for text in done.lines:
        print(text)
    source = scratch.source_of(found.args.safe_run, found.scratch, found.now)
    for text in (scratch.listing if listed else scratch.cleaning)(source):
        print(text)
    return done


def _repository_sections(
    found: Context, clock: timing.Clock, cleaned: account.Report
) -> tuple[Context, bool, Sequence[pulls.Read]]:
    runs = read_queue_runs(found)
    timing.lap(clock, "merge queue runs read")
    shared = functools.partial(runner_runs, found, runs)
    # Before the PRs are read: a draft's undraft check writes the first look.
    pressure = sweepline.pressure(
        found.github, shared(), found.settings.runners, found.now
    )
    read, waiting = _waiting(
        found.github,
        sweepline.open_pulls(found.github, found.settings, found.now, shared),
    )
    for said in waiting:
        print(said)
    timing.lap(clock, "pull requests read")
    found = dataclasses.replace(found, stands=pullmarks.pull_marks(found, read))
    broken = _pull_section(found, runs, read)
    timing.lap(clock, "pull requests done")
    report.print_queue(pressure, runs, found.settings, found.now)
    timing.lap(clock, "merge queue done")
    localsections.print_stragglers(
        found.args.safe_run, found.settings.project.workspace
    )
    for line in diskline.lines(cleaned, found.clean.min_free_gib):
        print(line)
    timing.lap(clock, "checkouts done")
    return found, broken, read


def _slot_section(found: Context, read: Sequence[pulls.Read]) -> None:
    report.print_reminders(found.settings)
    written = ledger.configured(found.settings)
    book = slotholding.derived(written, found.args.running)
    scope = offering.Look(opened=read, marks=found.stands)
    offer = slotholding.counted(
        offering.offered(found, scope, book), read, book, found.args
    )
    slotreport.print_ledger(book, offer.occupancy)
    sweepline.slots(read, offer, offering.disagreements(found, offer))
    sweepline.logged(book, offer, found.settings.slots.log, found.now)
    workerlines.print_lines(written, found.now, found.args, found.settings.slots)
    undrafts = readyline.texts(found.settings, pullmarks.awake(read, offer), found.now)
    unlabeled.print_lines(found.github, found.settings)
    tasklist.print_block(book, list(undrafts), offer.items, offer.occupancy)
    for line in tasklist.live_lines(book, read):
        print(line)


def _unledgered_section(found: Context) -> None:
    # keyword: action-matrix (promise#73): events no pitboss act record answers
    since = found.now - datetime.timedelta(days=1)
    for said in unledgered.lines(
        found.github, found.settings, found.settings.slots.log, since
    ):
        print(said)


def sweep_sections(found: Context, clock: timing.Clock) -> bool:
    """Report on PRs, runner pressure, queue runs, stragglers, worktrees, slots, LOG.

    Args:
        found: the context, loaded with the clocked arguments.
        clock: the sweep's clock.

    Returns:
        True for a failed check, a conflict, or an unread repository.
    """
    args = found.args
    where = configfile.locate(configfile.named(args), working_directory(args))
    ledgerowner.say_sweep(load_settings(args), where)
    localsections.print_update_check(args.safe_run)
    timing.lap(clock, "update check and configuration read")
    cleaned = _clean_section(found)
    timing.lap(clock, "cleaning done")
    found, broken, read = _repository_sections(found, clock, cleaned)
    _slot_section(found, read)
    summaryline.print_lines(
        found.github, found.settings, configfile.named(args), found.now
    )
    _unledgered_section(found)
    timing.lap(clock, "slots done")
    unconfigured = syncguard.unconfigured(args)
    crowded = tasklist.refused(args.task_list, found.settings.project.repo)
    failed = syncing.section(args, found.settings) or broken or unconfigured or crowded
    return bool(repoaccess.say(found.access) or failed)

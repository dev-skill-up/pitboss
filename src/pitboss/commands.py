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
    ENTRY_DATA,
    account,
    autoclean,
    cleanconfig,
    cleanjob,
    concurrently,
    config,
    configfile,
    dead,
    draftmoves,
    ghapi,
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
    workerlines,
    workhours,
)
from . import checkin, checkinlines, commanddoc, commandtext
from . import diskline, pulllines, pullstate, unlabeled, unreadableline
from .commandarguments import SWEEP_ARGUMENTS
from .failures import describe, read_all


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
    return sweepline.looked_pulls(found.github, found.settings, found.now, runs)


def load_context(args: argparse.Namespace) -> Context:
    """Load the configuration and set up the API.

    Args:
        args: the parsed arguments.

    Returns:
        The context.
    """
    logging.getLogger("commander_data.run").setLevel(logging.WARNING)
    now = timing.current_time(args)
    github = ghapi.GitHub(run=args.safe_run, mutate=args.run)
    start = working_directory(args)
    given = configfile.named(args)
    access = repoaccess.read(github, given, start)
    owner = access.settings.project.repo.owner
    return Context(
        settings=access.settings,
        access=access,
        clean=configfile.load_clean(given, start),
        scratch=configfile.load_scratch(given, start, owner),
        github=github,
        now=now,
        args=args,
    )


def read_queue_runs(found: Context) -> Sequence[queue.QueueRun]:
    """Read the queue runs of every repository whose PRs or runners are swept.

    Args:
        found: the context.

    Returns:
        The runs.
    """
    settings = found.settings
    repos = {
        repo.slug: repo
        for repo in (*settings.runners.repositories, *config.repositories(settings))
    }
    batches = concurrently.each(
        lambda repo: queue.read_runs(found.github, repo), repos.values()
    )
    return [each for batch in batches for each in batch]


def runner_runs(
    found: Context, runs: Sequence[queue.QueueRun]
) -> Sequence[queue.QueueRun]:
    """Keep the queue runs of the repositories that share the runners.

    Args:
        found: the context.
        runs: the runs of every repository read.

    Returns:
        The runs of the repositories under ``[runners]``.
    """
    sharing = {repo.slug for repo in found.settings.runners.repositories}
    return [each for each in runs if each.repo.slug in sharing]


def read_runner_runs(found: Context) -> Sequence[queue.QueueRun]:
    """Read the queue runs of the repositories that share the runners.

    Args:
        found: the context.

    Returns:
        The runs.
    """
    return runner_runs(found, read_queue_runs(found))


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
    shown = pulllines.lines(pull, found.now, found.settings, steps)
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
    read = sweepline.open_pulls(found.github, found.settings, found.now, shared)
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


def _first_item(found: Context) -> str:
    # the first queued item, read only when a slot is idle (pitboss#450)
    scope = offering.Look(opened=open_pulls(found), marks=found.stands)
    items = offering.offered(found, scope, ledger.configured(found.settings)).items
    return checkin.queue_text(
        [each.reference for each in items], configfile.named(found.args)
    )


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


@ENTRY_DATA.register(*SWEEP_ARGUMENTS, tasklist.ARGUMENT, name="sweep")
@commanddoc.described(commandtext.SWEEP)
def sweep(args: argparse.Namespace) -> None:
    """Report on PRs, runner pressure, queue runs, stragglers, worktrees, slots, LOG.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 for a failed check, a conflict, or an unread repository.
    """
    clock, args = timing.clocked(args)
    where = configfile.locate(configfile.named(args), working_directory(args))
    found = load_context(args)
    lapsed = checkinlines.print_first(found, functools.partial(_first_item, found))
    ledgerowner.say_sweep(load_settings(args), where)
    localsections.print_update_check(args.safe_run)
    cleaned = _clean_section(found)
    timing.lap(clock, "cleaning done")
    found, broken, read = _repository_sections(found, clock, cleaned)
    _slot_section(found, read)
    summaryline.print_lines(
        found.github, found.settings, configfile.named(args), found.now
    )
    timing.lap(clock, "slots done")
    unconfigured = syncguard.unconfigured(args)
    crowded = tasklist.refused(args.task_list, found.settings.project.repo)
    failed = syncing.section(args, found.settings) or broken or unconfigured or crowded
    if repoaccess.say(found.access) or failed or lapsed:
        raise SystemExit(1)

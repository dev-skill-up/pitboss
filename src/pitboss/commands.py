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
import random
import time
from typing import AbstractSet, Protocol, Sequence

from . import (
    account,
    answer,
    actrules,
    autoclean,
    cleanconfig,
    cleanjob,
    config,
    configfile,
    configloads,
    dead,
    diskline,
    ghclient,
    ghmemo,
    headchecks,
    ledger,
    ledgerowner,
    localsections,
    logline,
    machine as machines,
    project,
    pullchecks,
    queue,
    render,
    repoaccess,
    report,
    retrying,
    scratch,
    scratchconfig,
    slotholding,
    slotidle,
    slotlog,
    slotreport,
    slotsheader,
    summaryline,
    sweepline,
    syncguard,
    syncing,
    tasklist,
    timing,
    unlabeled,
    unledgered,
    workerlines,
    workhours,
    world,
)
from .running import KeywordRun
from .queuereads import read_queue_runs


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
    """

    settings: config.Config
    access: repoaccess.Access
    clean: cleanconfig.Clean
    scratch: scratchconfig.Scratch
    github: ghclient.GitHub
    now: datetime.datetime
    args: argparse.Namespace


working_directory = configfile.working_directory


class Seen(Protocol):
    """The one read of a command and its decisions (``onepath.Seen``)."""

    @property
    def made(self) -> world.World:
        """The world read.

        Returns:
            The world.
        """

    @property
    def decided(self) -> answer.Decided:
        """Its decisions.

        Returns:
            The decisions.
        """

    @property
    def runners(self) -> sweepline.Look:
        """The run's one look at the runners, which the read asked too.

        Returns:
            The look.
        """


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


def _reading(args: argparse.Namespace) -> KeywordRun:
    # keyword: read-retry: a read that may pass is tried again, then the command fails
    tried = retrying.with_retries(
        args.safe_run, functools.partial(random.uniform, 0.0), time.sleep
    )
    # keyword: read-memo (pitboss#453): a question of what is next reads a path once
    asks = {getattr(args, "action", None), getattr(args, "__gather_name__", None)}
    asks.add(getattr(args, "verb", None))  # act dispatch-next writes nothing to GitHub
    return ghmemo.memoized(tried) if asks & {"next", "dispatch-next"} else tried


def load_context(args: argparse.Namespace) -> Context:
    """Load the configuration and set up the API.

    Args:
        args: the parsed arguments.

    Returns:
        The context.
    """
    logging.getLogger("commander_data.run").setLevel(logging.WARNING)
    now = timing.current_time(args)
    github = ghclient.GitHub(run=_reading(args), mutate=args.run)
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
        clean=configloads.load_clean(given, start),
        scratch=configloads.load_scratch(given, start, owner),
        github=github,
        now=now,
        args=args,
    )


def _pull_section(runs: Sequence[queue.QueueRun], seen: Seen) -> bool:
    # keyword: one-path: each open pull request's facts, then its decision
    newest = queue.newest_by_reference(runs)
    decided = project.by_item(seen.decided)
    broken = False
    for record in world.pull_records(seen.made):
        pull = record.facts
        print(report.pull_line(pull, newest), flush=True)
        for line in render.item_lines(decided, record.row.reference):
            print(line)
        unanswered = headchecks.unanswered(pull.checks, pull.signals)
        broken = pullchecks.conflicted(pull) or bool(unanswered) or broken
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
    found: Context, clock: timing.Clock, cleaned: account.Report, seen: Seen
) -> bool:
    runs = read_queue_runs(found)
    timing.lap(clock, "merge queue runs read")
    # keyword: one-path: the look the read made, said once
    pressure = sweepline.pressure(seen.runners, found.settings.runners)
    broken = _pull_section(runs, seen)
    timing.lap(clock, "pull requests done")
    report.print_queue(pressure, runs, found.settings, found.now)
    timing.lap(clock, "merge queue done")
    localsections.print_stragglers(
        found.args.safe_run, found.settings.project.workspace
    )
    for line in diskline.lines(cleaned, found.clean.min_free_gib):
        print(line)
    timing.lap(clock, "checkouts done")
    return broken


def _slot_section(found: Context, seen: Seen) -> None:
    # keyword: one-path: the ledger, then what is next as the one answer says it
    report.print_reminders(found.settings)
    written = ledger.configured(found.settings)
    book = slotholding.derived(written, found.args.running)
    slotreport.print_ledger(book, slotholding.occupy(book, found.args.running))
    given = project.what_next(seen.decided)
    idle = _idle(found, book, given)
    logline.after([*render.answer_lines(given), *idle], found.settings.slots.log)
    workerlines.print_lines(written, found.now, found.args, found.settings.slots)
    unlabeled.print_lines(found.github, found.settings)
    # no slot is in flight while the running agents are not known (pitboss#94)
    named = [] if found.args.running is None else slotsheader.running(book)
    tasklist.print_block(book, given, named)
    facts = [each.facts for each in world.pull_records(seen.made)]
    for line in tasklist.live_lines(book, facts):
        print(line)


def _idle(found: Context, book: ledger.Ledger, given: answer.Answer) -> Sequence[str]:
    # keyword: slot-idle: a slot empty too long (so free) while there is work
    work = isinstance(given, answer.Work) and found.args.running is not None
    log = found.settings.slots.log
    return slotidle.lines(book, slotlog.read(log), found.now) if work else []


def _closing_sections(found: Context) -> None:
    summaryline.print_lines(
        found.github, found.settings, configfile.named(found.args), found.now
    )
    _unledgered_section(found)
    # what each actor writes, from the checker's own table (keyword: total-routes)
    print(actrules.instructions(), end="")


def _unledgered_section(found: Context) -> None:
    # keyword: action-matrix (promise#73): events no pitboss act record answers
    since = found.now - datetime.timedelta(days=1)
    for said in unledgered.lines(
        found.github, found.settings, found.settings.slots.log, since
    ):
        print(said)


def sweep_sections(found: Context, clock: timing.Clock, seen: Seen) -> bool:
    """Report on PRs, runner pressure, queue runs, stragglers, worktrees, slots, LOG.

    Args:
        found: the context, loaded with the clocked arguments.
        clock: the sweep's clock.
        seen: the one read of the sweep and its decisions (keyword: one-path).

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
    broken = _repository_sections(found, clock, cleaned, seen)
    _slot_section(found, seen)
    _closing_sections(found)
    timing.lap(clock, "slots done")
    unconfigured = syncguard.unconfigured(args)
    crowded = tasklist.refused(args.task_list, found.settings.project.repo)
    failed = syncing.section(args, found.settings) or broken or unconfigured or crowded
    return bool(repoaccess.say(found.access) or failed)

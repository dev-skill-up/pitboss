"""The commands: thin wrappers that read, decide with the other modules, and print.

Reads go through ``args.safe_run``; changes through ``args.run``, which is
a dry run unless ``--no-dry-run`` is given.
"""

import argparse
import concurrent.futures
import dataclasses
import datetime
import logging
import os
import pathlib
import subprocess
import time
from typing import AbstractSet, Mapping, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    cleanconfig,
    config,
    configfile,
    dead,
    ghapi,
    handback,
    ledger,
    local,
    pulls,
    queue,
    report,
    sweepline,
    timing,
    tracefs,
    work,
    worktrees,
)
from . import diskline, repoarg, roundline, stall, updateline
from .failures import describe, read_all
from .markers import Marker

CONFIG_ARGUMENT = add_argument(
    "config", help="a path, or a name in .claude/pitboss/<name>.toml"
)
NOW_ARGUMENT = add_argument("--now", default=None, help=argparse.SUPPRESS)
DRY_RUN_ARGUMENT = add_argument("--no-dry-run", action="store_true", default=False)
CHANGING_ARGUMENTS = (CONFIG_ARGUMENT, NOW_ARGUMENT, DRY_RUN_ARGUMENT)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Context:
    """What every command starts from.

    Attributes:
        settings: the configuration.
        clean: what ``clean-container`` looks at and keeps.
        github: the API.
        now: the time now.
        args: the parsed arguments.
    """

    settings: config.Config
    clean: cleanconfig.Clean
    github: ghapi.GitHub
    now: datetime.datetime
    args: argparse.Namespace


def working_directory(args: argparse.Namespace) -> pathlib.Path:
    """The directory a configuration name is looked up from.

    Args:
        args: the parsed arguments.

    Returns:
        ``PWD`` of the environment, else the current directory.
    """
    return pathlib.Path(args.env.get("PWD", "."))


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
    return configfile.load(args.config, working_directory(args))


def open_pulls(found: Context) -> Sequence[pulls.PullFacts]:
    """Read every open PR the configuration names.

    Args:
        found: the context.

    Returns:
        The PRs.
    """
    return pulls.read_open(found.github, found.settings)


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
    return Context(
        settings=readable(github, load_settings(args)),
        clean=configfile.load_clean(args.config, working_directory(args)),
        github=github,
        now=now,
        args=args,
    )


def _without(settings: config.Config, failures: Mapping[str, str]) -> config.Config:
    runners = settings.runners
    return dataclasses.replace(
        settings,
        libraries=[repo for repo in settings.libraries if repo.slug not in failures],
        runners=dataclasses.replace(
            runners,
            repositories=[
                repo for repo in runners.repositories if repo.slug not in failures
            ],
        ),
    )


def readable(github: ghapi.GitHub, settings: config.Config) -> config.Config:
    """Leave out, and report, the libraries this session cannot read.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        The configuration without them.

    Raises:
        SystemExit: when the project's own repository cannot be read.
    """
    shared = settings.runners.repositories
    wanted = [repo.slug for repo in (*config.repositories(settings), *shared)]
    failures = ghapi.unreadable(github, wanted)
    for slug, reason in failures.items():
        print(
            f"{Marker.UNREADABLE.text} {slug}: {reason}: give the session access"
            " or take it out of the configuration; swept without it"
        )
    if settings.project.repo.slug in failures:
        raise SystemExit(f"cannot read {settings.project.repo.slug}")
    return _without(settings, failures)


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
    with concurrent.futures.ThreadPoolExecutor() as pool:
        batches = pool.map(
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


def _pull_section(found: Context, runs: Sequence[queue.QueueRun]) -> bool:
    newest = queue.newest_by_reference(runs)
    broken = False
    for pull in open_pulls(found):
        print(report.pull_line(pull, newest))
        latest = newest.get(pulls.reference(pull))
        queued = latest is not None and not latest.run.finished
        read = read_all(found.github, pull)
        why = {check_id: describe(failure) for check_id, failure in read.items()}
        steps = {check_id: failure.steps for check_id, failure in read.items()}
        for line in stall.lines(pull, found.now, steps):
            print(line)
        for line in updateline.lines(pull, found.settings):
            print(line)
        for line in roundline.lines(pull):
            print(line)
        for line in report.action_lines(pull, found.settings, queued, why):
            print(line)
        broken = broken or pulls.conflicted(pull) or bool(pulls.failed_checks(pull))
    return broken


def _straggler_section(found: Context) -> None:
    run = found.args.safe_run
    found_checkouts = local.checkouts(found.settings.project.workspace)
    for failed in local.fetch_each_repository(run, found_checkouts):
        print(f"fetch failed in {failed}: its stragglers may be out of date")
    for checkout in found_checkouts:
        straggler = local.read_straggler(run, checkout)
        if straggler is not None:
            print(report.straggler_line(straggler))
    print("stragglers: sweep done")


def _queue_section(found: Context, runs: Sequence[queue.QueueRun]) -> None:
    shared = runner_runs(found, runs)
    print(sweepline.pressure(found.github, shared, found.settings.runners, found.now))
    for line in report.queue_lines(runs, found.settings, found.now):
        print(line)


def _look(found: Context) -> dead.Look:
    return dead.Look(
        run=found.args.safe_run,
        github=found.github,
        settings=found.settings,
        clean=found.clean,
        working=running_in(found.args),
    )


def _worktree_section(found: Context) -> None:
    look = _look(found)
    if found.clean.worktrees is cleanconfig.Worktrees.AUTO:
        # A sweep that removes: safe_run really runs (keyword: clean-worktrees).
        lines = worktrees.remove_lines(
            look, worktrees.Action(run=found.args.safe_run, dry=False), found.now
        )
    else:
        lines = worktrees.stale_lines(look, found.now)
    for text in lines:
        print(text)


def _disk_section(found: Context) -> None:
    for text in diskline.lines(_look(found), found.now):
        print(text)


@ENTRY_DATA.register(CONFIG_ARGUMENT, NOW_ARGUMENT, name="sweep")
def sweep(args: argparse.Namespace) -> None:
    """Report on PRs, runner pressure, queue runs, stragglers, worktrees, slots.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when a PR has a failed check or a merge conflict.
    """
    tracefs.say(args.safe_run)
    found = load_context(args)
    clock = timing.Clock(started=time.monotonic())
    runs = read_queue_runs(found)
    broken = _pull_section(found, runs)
    timing.lap(clock, "pull requests done")
    _queue_section(found, runs)
    timing.lap(clock, "merge queue done")
    _straggler_section(found)
    _worktree_section(found)
    _disk_section(found)
    timing.lap(clock, "checkouts done")
    for line in report.reminder_lines(found.settings):
        print(line)
    book = read_ledger(found.settings)
    report.print_ledger(book)
    queued = work.queued(open_pulls(found), found.github, found.settings, book)
    report.print_free_slots(book, len(queued))
    handback.print_lines(book, found.now)
    if broken:
        raise SystemExit(1)


def read_ledger(settings: config.Config) -> ledger.Ledger:
    """Read the configured ledger.

    Args:
        settings: the configuration.

    Returns:
        The ledger.
    """
    return ledger.read(settings.slots.ledger, settings.slots.default)


@ENTRY_DATA.register(*CHANGING_ARGUMENTS, name="cancel-stale-runs")
def cancel_stale_runs(args: argparse.Namespace) -> None:
    """Cancel the queue runs that are not the newest group of their PR.

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    verb = "" if args.no_dry_run else " (dry run: --no-dry-run cancels it)"
    for stale in queue.stale_runs(read_queue_runs(found)):
        name = f"{stale.repo.slug} {stale.run.id}"
        try:
            path = f"repos/{stale.repo.slug}/actions/runs/{stale.run.id}/cancel"
            ghapi.post(found.github, path)
        except subprocess.CalledProcessError:
            print(f"{Marker.COULD_NOT_CANCEL_STALE_QUEUE_RUN.text} {name}")
            continue
        print(f"{Marker.CANCELLED_STALE_QUEUE_RUN.text} {name}{verb}")


@ENTRY_DATA.register(*CHANGING_ARGUMENTS, name="clean-worktrees")
def clean_worktrees(args: argparse.Namespace) -> None:
    """Remove the finished worktrees that pass the safety test (branches are kept).

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    how = worktrees.Action(run=args.run, dry=not args.no_dry_run)
    for text in worktrees.remove_lines(_look(found), how, found.now):
        print(text)


@ENTRY_DATA.register(CONFIG_ARGUMENT, add_argument("repository"), name="review-form")
def review_form(args: argparse.Namespace) -> None:
    """Print the form a review comment in a repository must take.

    Args:
        args: the parsed arguments.
    """
    settings = load_settings(args)
    repo = repoarg.named_repo(args.repository, settings)
    gated = repo.slug in settings.review.gated
    form = settings.review.gated_form if gated else settings.review.form
    print(f"# {repo.slug}: {'gated' if gated else 'not gated'}")
    print(
        f"# {{sha}}: the full head SHA; {{verdict}}: {form.approved!r} or"
        f" {form.changes_needed!r}"
    )
    if gated:
        print(
            "# first line exactly as below; each line below once; ASCII only;"
            " no code fences, HTML or link definitions"
        )
    for line in form.lines:
        print(line)

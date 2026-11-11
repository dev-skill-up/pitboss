"""The ``clean-container`` command: remove what is dead, in parts."""

import argparse
import dataclasses
import functools
import pathlib
from typing import AbstractSet, Callable, Sequence

from gather.commands import add_argument

from . import (
    commanddoc,
    commandtext,
    ENTRY_DATA,
    cleaning,
    cleanjob,
    container,
    dead,
    deadscan,
    disk,
    logline,
    named,
    scanning,
    tempclean,
    timing,
    workhours,
    worktrees,
)
from .commandarguments import CHANGING_ARGUMENTS
from .commands import (
    Context,
    load_context,
    running_in,
    sweep_look,
)
from .machine import Machine, real as real_filesystem, real_machine

TMP_PATTERN = "tmp*"
DEFAULT_TMP_HOURS = 2.0
FETCH_FAILED = "fetch failed in {}: its repository's checkouts are not judged"


def look_of(args: argparse.Namespace, found: Context) -> dead.Look:
    """What looking at the machine needs, from the arguments.

    Args:
        args: the parsed arguments.
        found: the configuration and the API.

    Returns:
        The look.
    """
    watch = container.Watch(
        marker=pathlib.Path(args.marker),
        root=pathlib.Path(args.root),
        hours=args.hours,
    )
    walks = scanning.memo(real_filesystem().inspect)
    return dead.Look(
        run=args.safe_run,
        github=found.github,
        settings=found.settings,
        clean=found.clean,
        watch=watch,
        working=running_in(args),
        marker_expiry=workhours.expiry_of(found.now),
        scan=scanning.Scanning(lap=functools.partial(timing.note, args), walks=walks),
    )


def roots_of(
    look: dead.Look, places: AbstractSet[pathlib.Path]
) -> AbstractSet[pathlib.Path]:
    """The directories whose entries ``clean-container`` may remove.

    Args:
        look: what to look at and keep.
        places: the directories under the workspace that hold a dead checkout.

    Returns:
        The workspace, the scratch directories, the root of the files, the
        tempdir roots and the places.
    """
    return {*cleanjob.roots(look), *look.clean.tmp_roots, *places}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Tempdirs:
    """The test tempdirs ``clean-container`` looks at.

    Attributes:
        machine: the machine.
        hours: how long a tempdir must be untouched.
        free: the idle tempdirs that may go.
        used: the idle tempdirs a running process works in.
        paths: the paths of ``free``.
    """

    machine: Machine
    hours: float
    free: Sequence[dead.Candidate]
    used: Sequence[dead.Candidate]
    paths: AbstractSet[pathlib.Path]


def tempdirs_of(args: argparse.Namespace, look: dead.Look, found: Context) -> Tempdirs:
    """Look at the test tempdirs: ``tmp*`` in the tempdir roots, idle for the hours.

    Args:
        args: the parsed arguments.
        look: what to look at and keep.
        found: the configuration and the API.

    Returns:
        The tempdirs.
    """
    machine = real_machine(args.env, found.now, running_in(args), args.usage)
    # a path two lists name is walked once (keyword: walk-speed)
    kept = dataclasses.replace(
        machine.fs, inspect=look.scan.walks or machine.fs.inspect
    )
    remembering = dataclasses.replace(machine, fs=kept)
    patterns = (TMP_PATTERN, *look.clean.tmp_patterns)
    clean = dataclasses.replace(look.clean, tmp_patterns=patterns)
    free, used = tempclean.split_tempdirs(remembering, clean, args.tmp_hours)
    paths = {each.path for each in free}
    look.scan.lap("test tempdirs judged", len(free))
    return Tempdirs(
        machine=machine, hours=args.tmp_hours, free=free, used=used, paths=paths
    )


def recheck_of(
    look: dead.Look, cutoff: float, tempdirs: Tempdirs, each: dead.Candidate
) -> str:
    """Look again, just before the removal, at a path that was listed.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.
        tempdirs: the test tempdirs.
        each: the candidate.

    Returns:
        Why the path must not be removed now, or empty when it may.
    """
    if each.path in tempdirs.paths:
        return tempclean.recheck(tempdirs.machine, tempdirs.hours, each)
    return dead.recheck(look, cutoff, each)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Removing:
    """What ``clean-container`` is to remove, and from where.

    Attributes:
        listed: the dead paths.
        roots: the directories whose entries may be removed.
        recheck: why a path must not be removed now, looked at just before.
    """

    listed: Sequence[dead.Candidate]
    roots: AbstractSet[pathlib.Path]
    recheck: Callable[[dead.Candidate], str]


def remove_listed(
    args: argparse.Namespace, look: dead.Look, removing: Removing
) -> cleaning.Outcome:
    """Remove the safe (and approved) dead paths, saying what happened to each.

    Each is looked at again just before its removal.

    Args:
        args: the parsed arguments.
        look: what to look at and keep.
        removing: the dead paths, where they may go from, and how to look again.

    Returns:
        What was done.
    """
    approved = cleaning.read_approved(args.approved)
    chosen, refused = cleaning.choose(removing.listed, approved, removing.roots)
    use = functools.partial(args.usage, look.settings.project.workspace)
    before = use()
    gone = cleaning.remove_all(args, removing.recheck, chosen)
    cleaning.prune(args.run, gone)
    look.scan.lap("paths removed", len(gone), "paths")
    return cleaning.Outcome(
        gone=gone,
        kept=dead.unsafe(removing.listed),
        refused=refused,
        removing=args.no_dry_run,
        before=before,
        after=use(),
    )


ARGUMENTS = (
    *CHANGING_ARGUMENTS,
    add_argument("--marker", default=container.DEFAULT_MARKER),
    add_argument("--root", default=container.DEFAULT_ROOT),
    add_argument("--hours", type=float, default=container.DEFAULT_HOURS),
    add_argument("--tmp-hours", type=float, default=DEFAULT_TMP_HOURS),
    add_argument("--batch", type=cleaning.positive, default=cleaning.DEFAULT_BATCH),
    add_argument("--approved", default=None),
)


@ENTRY_DATA.register(*ARGUMENTS, name="clean-container")
@commanddoc.described(commandtext.CLEAN_CONTAINER)
def clean_container(args: argparse.Namespace) -> None:
    """Remove the dead paths: finished checkouts, idle scratch, session files.

    The dry run lists each dead path with its size and why it is dead, and
    lists apart the dead paths that are not safe (commits on no remote
    branch, changed tracked files) which are never removed. With
    ``--no-dry-run`` the safe ones are removed, at most ``--batch`` paths for
    each ``rm``; each path is looked at again just before its ``rm``.
    ``--approved FILE`` limits the removal to the paths listed in the file
    that are among the safe dead paths now.

    A checkout is found wherever git lists it under the workspace, of any
    repository, and is dead when its PR merged or closed, its tip is in the base
    branch, or a number in its name or branch is a closed ticket. The entries
    beside a dead checkout that are named for its ticket are dead too. Each
    checkout that is kept says why. Test tempdirs (``tmp*`` in the ``[clean]
    tmp_roots``) untouched for ``--tmp-hours`` (default 2) are removed, counted
    with their size; one a running process works in is named and kept. A path
    removed is marked ``FREED``.

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    look = look_of(args, found)
    scan, tempdirs, removing = plan_of(args, look, found)
    for text in leading_lines(scan, tempdirs):
        print(text)
    done = remove_listed(args, look, removing)
    for text in cleaning.closing_lines(done):
        print(text)
    log_freed(found, done)


def log_freed(found: Context, done: cleaning.Outcome) -> None:
    """Record in the log what a real run freed.

    Args:
        found: the configuration and the API.
        done: what the run did.
    """
    if done.removing:
        size = sum(each.size for each in done.gone)
        heads = [each.head for each in done.gone if each.head]
        freed = logline.Freed(who="pitboss clean-container", size=size, heads=heads)
        logline.record_clean(found.settings.slots.log, freed, found.now)


def unwalked(look: dead.Look) -> dead.Look:
    """The look of the removal: it looks at the disk again, not at the scan's walks.

    Args:
        look: what to look at and keep.

    Returns:
        The look without its remembered walks.
    """
    return dataclasses.replace(look, scan=scanning.Scanning(lap=look.scan.lap))


def plan_of(
    args: argparse.Namespace, look: dead.Look, found: Context
) -> tuple[deadscan.Findings, Tempdirs, Removing]:
    """Look at the machine: the dead paths, the test tempdirs, what to remove.

    Args:
        args: the parsed arguments.
        look: what to look at and keep.
        found: the configuration and the API.

    Returns:
        What the scan found, the test tempdirs and the removal.
    """
    now = found.now.timestamp()
    cutoff = now - look.settings.idle_hours * 3600
    scan = deadscan.scan(look, now)
    tempdirs = tempdirs_of(args, look, found)
    scratch = named.dead_named(look, cutoff, scan.places, scan.tickets)
    look.scan.lap("named scratch judged")
    return (
        scan,
        tempdirs,
        Removing(
            listed=dead.ordered([*scan.candidates, *scratch, *tempdirs.free]),
            roots=roots_of(look, scan.places),
            recheck=functools.partial(recheck_of, unwalked(look), cutoff, tempdirs),
        ),
    )


def leading_lines(scan: deadscan.Findings, tempdirs: Tempdirs) -> Sequence[str]:
    """What is said before the removals: fetches that failed, what is kept, tempdirs.

    Args:
        scan: what the scan found.
        tempdirs: the test tempdirs.

    Returns:
        The lines.
    """
    failed = list(map(FETCH_FAILED.format, scan.unfetched))
    checkouts = [each for each in scan.kept if each.why != dead.NOT_A_CHECKOUT]
    size = disk.size_text(sum(each.size for each in tempdirs.free))
    hours = f"{tempdirs.hours:g} hours"
    counted = f"clean: {len(tempdirs.free)} test tempdirs untouched for {hours}, {size}"
    return [
        *failed,
        *cleaning.kept_checkouts(checkouts),
        counted,
        *used_lines(tempdirs),
    ]


def used_lines(tempdirs: Tempdirs) -> Sequence[str]:
    """The lines that name the idle tempdirs a running process works in.

    Args:
        tempdirs: the test tempdirs.

    Returns:
        A line for each.
    """
    why = f"untouched for {tempdirs.hours:g} hours, but a running process works in it"
    return [
        f"clean: kept {each.path} {disk.size_text(each.size)} ({why})"
        for each in tempdirs.used
    ]


@ENTRY_DATA.register(*CHANGING_ARGUMENTS, name="clean-worktrees")
def clean_worktrees(args: argparse.Namespace) -> None:
    """Remove the finished worktrees that pass the safety test (branches are kept).

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    how = worktrees.Action(run=args.run, dry=not args.no_dry_run)
    done = worktrees.removal(sweep_look(found), how, found.now)
    for text in done.lines:
        print(text)
    if not how.dry:
        who = "pitboss clean-worktrees"
        freed = logline.Freed(who=who, size=done.freed, heads=done.heads)
        logline.record_clean(found.settings.slots.log, freed, found.now)

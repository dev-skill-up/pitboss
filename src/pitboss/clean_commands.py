"""The ``clean-container`` command: remove what is dead, in parts."""

import argparse
import dataclasses
import functools
import pathlib
from typing import AbstractSet, Callable, Sequence

from gather.commands import add_argument

from . import (
    ENTRY_DATA,
    cleaning,
    cleanjob,
    container,
    dead,
    deadscan,
    disk,
    named,
    tempclean,
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
from .machine import Machine, real_machine

TMP_PATTERN = "tmp*"
DEFAULT_TMP_HOURS = 2.0


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
    return dead.Look(
        run=args.safe_run,
        github=found.github,
        settings=found.settings,
        clean=found.clean,
        watch=watch,
        working=running_in(args),
        marker_expiry=workhours.expiry_of(found.now),
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


def recheck_of(
    look: dead.Look,
    machine: Machine,
    cutoffs: tuple[float, float],
    tempdirs: AbstractSet[pathlib.Path],
    each: dead.Candidate,
) -> str:
    """Look again, just before the removal, at a path that was listed.

    Args:
        look: what to look at and keep.
        machine: the machine.
        cutoffs: the time before which a path is idle, and the hours of a tempdir.
        tempdirs: the paths that are tempdirs.
        each: the candidate.

    Returns:
        Why the path must not be removed now, or empty when it may.
    """
    cutoff, hours = cutoffs
    if each.path in tempdirs:
        return tempclean.recheck(machine, hours, each)
    return dead.recheck(look, cutoff, each)


def remove_listed(
    args: argparse.Namespace,
    look: dead.Look,
    listed: Sequence[dead.Candidate],
    how: tuple[AbstractSet[pathlib.Path], Callable[[dead.Candidate], str]],
) -> cleaning.Outcome:
    """Remove the safe (and approved) dead paths, saying what happened to each.

    Each is looked at again just before its removal.

    Args:
        args: the parsed arguments.
        look: what to look at and keep.
        listed: the dead paths.
        how: the directories whose entries may be removed, and the look at a
            path just before its removal.

    Returns:
        What was done.
    """
    roots, recheck = how
    approved = cleaning.read_approved(args.approved)
    chosen, refused = cleaning.choose(listed, approved, roots)
    workspace = look.settings.project.workspace
    before = args.usage(workspace)
    gone = cleaning.remove_all(args, recheck, chosen)
    cleaning.prune(args.run, gone)
    return cleaning.Outcome(
        gone=gone,
        kept=dead.unsafe(listed),
        refused=refused,
        removing=args.no_dry_run,
        before=before,
        after=args.usage(workspace),
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
    now = found.now.timestamp()
    cutoff = now - look.settings.idle_hours * 3600
    machine = real_machine(args.env, found.now, running_in(args), args.usage)
    scan = deadscan.scan(look, now)
    patterns = (TMP_PATTERN, *look.clean.tmp_patterns)
    clean = dataclasses.replace(look.clean, tmp_patterns=patterns)
    free, used = tempclean.split_tempdirs(machine, clean, args.tmp_hours)
    listed = dead.ordered(
        [*scan.candidates, *named.dead_named(look, cutoff, scan), *free]
    )
    recheck = functools.partial(
        recheck_of,
        look,
        machine,
        (cutoff, args.tmp_hours),
        {each.path for each in free},
    )
    for name in scan.unfetched:
        print(f"fetch failed in {name}: its repository's checkouts are not judged")
    for text in kept_lines(scan.kept, used, args.tmp_hours):
        print(text)
    print(tempdirs_line(free, args.tmp_hours))
    done = remove_listed(args, look, listed, (roots_of(look, scan.places), recheck))
    for text in cleaning.closing_lines(done):
        print(text)


def kept_lines(
    kept: Sequence[dead.Kept], used: Sequence[dead.Candidate], hours: float
) -> Sequence[str]:
    """The lines that say why a checkout or a tempdir is not removed.

    Args:
        kept: the directories of the workspace the scan left, each with why.
        used: the idle tempdirs a running process works in.
        hours: how long a tempdir must be untouched.

    Returns:
        A line for each checkout kept and each tempdir used; a directory that
        is no checkout is not named.
    """
    checkouts = [each for each in kept if each.why != deadscan.NOT_A_CHECKOUT]
    why = f"untouched for {hours:g} hours, but a running process works in it"
    return [
        *(f"clean: kept {each.path} ({each.why})" for each in checkouts),
        *(
            f"clean: kept {each.path} {disk.size_text(each.size)} ({why})"
            for each in used
        ),
    ]


def tempdirs_line(free: Sequence[dead.Candidate], hours: float) -> str:
    """The line that counts the test tempdirs to remove, and their size.

    Args:
        free: the idle tempdirs that may go.
        hours: how long a tempdir must be untouched.

    Returns:
        The line.
    """
    size = disk.size_text(sum(each.size for each in free))
    return f"clean: {len(free)} test tempdirs untouched for {hours:g} hours, {size}"


@ENTRY_DATA.register(*CHANGING_ARGUMENTS, name="clean-worktrees")
def clean_worktrees(args: argparse.Namespace) -> None:
    """Remove the finished worktrees that pass the safety test (branches are kept).

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    how = worktrees.Action(run=args.run, dry=not args.no_dry_run)
    for text in worktrees.remove_lines(sweep_look(found), how, found.now):
        print(text)

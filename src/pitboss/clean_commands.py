"""The ``clean-container`` command: remove what is dead, in parts."""

import argparse
import functools
import pathlib
from typing import AbstractSet, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, cleaning, container, dead, deadscan, disk
from .commands import CHANGING_ARGUMENTS, Context, load_context, running_in


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
    )


def roots_of(look: dead.Look) -> AbstractSet[pathlib.Path]:
    """The directories whose entries ``clean-container`` may remove.

    Args:
        look: what to look at and keep.

    Returns:
        The workspace, the scratch directories and the root of the files.
    """
    return {look.settings.project.workspace, *look.clean.scratch, look.watch.root}


def remove_listed(
    args: argparse.Namespace,
    look: dead.Look,
    listed: Sequence[dead.Candidate],
    now: float,
) -> cleaning.Outcome:
    """Remove the safe (and approved) dead paths, saying what happened to each.

    Each is looked at again just before its removal.

    Args:
        args: the parsed arguments.
        look: what to look at and keep.
        listed: the dead paths.
        now: seconds since the epoch.

    Returns:
        What was done.
    """
    approved = cleaning.read_approved(args.approved)
    chosen, refused = cleaning.choose(listed, approved, roots_of(look))
    cutoff = now - look.settings.idle_hours * 3600
    workspace = look.settings.project.workspace
    before = disk.free_space(workspace)
    recheck = functools.partial(dead.recheck, look, cutoff)
    gone = cleaning.remove_all(args, recheck, chosen)
    cleaning.prune(args.run, gone)
    return cleaning.Outcome(
        gone=gone,
        kept=dead.unsafe(listed),
        refused=refused,
        removing=args.no_dry_run,
        before=before,
        after=disk.free_space(workspace),
    )


ARGUMENTS = (
    *CHANGING_ARGUMENTS,
    add_argument("--marker", default=container.DEFAULT_MARKER),
    add_argument("--root", default=container.DEFAULT_ROOT),
    add_argument("--hours", type=float, default=container.DEFAULT_HOURS),
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

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    look = look_of(args, found)
    now = found.now.timestamp()
    scan = deadscan.scan(look, now)
    for name in scan.unfetched:
        print(f"fetch failed in {name}: its repository's checkouts are not judged")
    done = remove_listed(args, look, scan.candidates, now)
    for text in cleaning.closing_lines(done):
        print(text)

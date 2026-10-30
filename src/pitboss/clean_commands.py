"""The ``clean-container`` command: remove what is dead, in parts."""

import argparse
import pathlib
from typing import Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, cleaning, dead, deadscan, disk
from .commands import CHANGING_ARGUMENTS, load_context


def remove_listed(
    args: argparse.Namespace, look: dead.Look, listed: Sequence[dead.Candidate]
) -> cleaning.Outcome:
    """Remove the safe (and approved) dead paths, saying what happened to each.

    Args:
        args: the parsed arguments.
        look: what to look at and keep.
        listed: the dead paths.

    Returns:
        What was done.
    """
    chosen, refused = cleaning.choose(listed, cleaning.read_approved(args.approved))
    workspace = look.settings.project.workspace
    before = disk.free_space(workspace)
    gone = cleaning.remove_all(args, chosen)
    cleaning.prune(args.run, gone)
    return cleaning.Outcome(
        gone=gone,
        kept=dead.unsafe(listed),
        refused=refused,
        removing=args.no_dry_run,
        before=before,
        after=disk.free_space(workspace),
    )


def list_dead(
    args: argparse.Namespace, look: dead.Look, now: float
) -> tuple[Sequence[str], Sequence[dead.Candidate]]:
    """Find the dead paths: checkouts, scratch and files in the root.

    Args:
        args: the parsed arguments.
        look: what to look at and keep.
        now: seconds since the epoch.

    Returns:
        The checkouts that could not be fetched, and the dead paths.
    """
    scan = deadscan.scan(look, now)
    root, marker = pathlib.Path(args.root), pathlib.Path(args.marker)
    files = dead.dead_root_files(marker, root, args.hours)
    return scan.unfetched, dead.ordered([*scan.candidates, *files])


ARGUMENTS = (
    *CHANGING_ARGUMENTS,
    add_argument("--marker", default="/container_info.json"),
    add_argument("--root", default="/"),
    add_argument("--hours", type=float, default=1.0),
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
    each ``rm``. ``--approved FILE`` limits the removal to the paths listed in
    the file, each again checked safe.

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    look = dead.Look(
        run=args.safe_run,
        github=found.github,
        settings=found.settings,
        clean=found.clean,
    )
    unfetched, listed = list_dead(args, look, found.now.timestamp())
    for name in unfetched:
        print(f"fetch failed in {name}: its repository's checkouts are not judged")
    for text in cleaning.closing_lines(remove_listed(args, look, listed)):
        print(text)

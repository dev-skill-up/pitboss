"""What ``clean-container`` does with the dead paths: choose, remove in parts, say."""

import argparse
import contextlib
import dataclasses
import itertools
import os
import pathlib
import subprocess
from typing import AbstractSet, Callable, Iterator, Sequence

from . import dead, disk
from .markers import Marker
from .running import Run, git

DEFAULT_BATCH = 5


def positive(text: str) -> int:
    """Read a count of paths for one ``rm``.

    Args:
        text: the argument.

    Returns:
        The count.

    Raises:
        argparse.ArgumentTypeError: when it is not a whole number above 0.
    """
    if not text.isdigit() or int(text) < 1:
        raise argparse.ArgumentTypeError(f"{text!r} is not a count above 0")
    return int(text)


def read_approved(path: str | None) -> AbstractSet[pathlib.Path] | None:
    """Read the paths the orchestrator approved.

    Args:
        path: a file with one path on each line (blank lines and ``#`` lines
            are skipped), or None for no list.

    Returns:
        The paths, or None when there is no list.
    """
    if path is None:
        return None
    lines = (line.strip() for line in pathlib.Path(path).read_text().splitlines())
    return {pathlib.Path(line) for line in lines if line and not line.startswith("#")}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Removal:
    """How paths are removed.

    Attributes:
        run: the runner for changes.
        recheck: why a path must not be removed now, or empty.
        batch: the most paths in one call.
        dry: whether the runner does nothing.
    """

    run: Run
    recheck: Callable[[dead.Candidate], str]
    batch: int
    dry: bool


def left_behind(each: dead.Candidate) -> str:
    """Why a path is still there after its ``rm``.

    Args:
        each: the candidate.

    Returns:
        Empty when it is gone.
    """
    return "rm left it in place" if os.path.lexists(each.path) else ""


def removals(
    how: Removal, paths: Sequence[dead.Candidate]
) -> Iterator[tuple[dead.Candidate, str]]:
    """Remove paths with one ``rm -rf`` for each part of at most ``batch``.

    Each part is looked at again just before its ``rm`` (an agent may have
    started in a path since the listing, or a commit been made in it), and
    ``rm`` stays on one file system: a mount point in a path is not emptied.

    Args:
        how: how to remove them.
        paths: the candidates.

    Yields:
        Each candidate, and why it is still there (empty when it is gone, as
        a dry run would leave it).
    """
    for part in itertools.batched(paths, how.batch):
        checked = [(each, "" if how.dry else how.recheck(each)) for each in part]
        going = [str(each.path) for each, why in checked if not why]
        if going:
            with contextlib.suppress(subprocess.CalledProcessError):
                how.run(["rm", "-rf", "--one-file-system", "--", *going])
        for each, why in checked:
            yield each, why or ("" if how.dry else left_behind(each))


def prune(run: Run, gone: Sequence[dead.Candidate]) -> None:
    """Prune the worktree lists that a removed linked worktree was in.

    A git directory that is itself gone (the checkout holding it was removed
    in the same run) has no list left to prune, so it is skipped.

    Args:
        run: the runner for changes.
        gone: the removed candidates.
    """
    for directory in sorted({each.prune for each in gone if each.prune}, key=str):
        if not directory.exists():
            continue
        git(run, directory, "worktree", "prune")


def choose(
    listed: Sequence[dead.Candidate],
    approved: AbstractSet[pathlib.Path] | None,
    roots: AbstractSet[pathlib.Path],
) -> tuple[Sequence[dead.Candidate], Sequence[pathlib.Path]]:
    """The safe candidates to remove, and the paths named that are not.

    Only a path directly in a configured root is ever removed, and an approved
    path is removed only when it is one of the safe candidates now: any other
    path of the file is refused, whatever it is.

    Args:
        listed: the dead paths.
        approved: the paths approved, or None for every safe one.
        roots: the directories whose entries may be removed.

    Returns:
        The candidates to remove, and the approved paths (or, with no list,
        the safe candidates) that are not removed because they are no safe
        dead path directly in a root.
    """
    safe = dead.safe(listed)
    placed = [each for each in safe if each.path.parent in roots]
    chosen = placed if approved is None else [e for e in placed if e.path in approved]
    named = {each.path for each in safe} if approved is None else approved
    return chosen, sorted(named - {each.path for each in chosen})


def path_line(marker: Marker, each: dead.Candidate, tail: str) -> str:
    """The line about a path: marker, path, size, why it is dead, then a tail.

    Args:
        marker: the marker the line starts with.
        each: the candidate.
        tail: what follows the reason.

    Returns:
        The line.
    """
    size = disk.size_text(each.size)
    return f"{marker.text} {each.path} {size} ({each.reason}){tail}"


def kept_line(each: dead.Candidate) -> str:
    """The line for a dead path that is kept.

    Args:
        each: the candidate.

    Returns:
        The line.
    """
    return path_line(Marker.KEPT_PATH, each, f": {each.kept}")


def removed_line(each: dead.Candidate, verb: str) -> str:
    """The line for a path that was removed.

    Args:
        each: the candidate.
        verb: the dry run note, or empty.

    Returns:
        The line.
    """
    return path_line(Marker.REMOVED_PATH, each, verb)


def stuck_line(each: dead.Candidate, why: str) -> str:
    """The line for a path that is still there.

    Args:
        each: the candidate.
        why: why it was not removed, or why ``rm`` left it.

    Returns:
        The line.
    """
    return path_line(Marker.COULD_NOT_REMOVE_PATH, each, f": {why}")


def remove_all(
    args: argparse.Namespace,
    recheck: Callable[[dead.Candidate], str],
    chosen: Sequence[dead.Candidate],
) -> Sequence[dead.Candidate]:
    """Remove the chosen paths in parts, saying what happened to each.

    Args:
        args: the parsed arguments.
        recheck: why a path must not be removed now, or empty.
        chosen: the safe paths to remove.

    Returns:
        The paths that are gone (all of them in a dry run).
    """
    verb = "" if args.no_dry_run else " (dry run: --no-dry-run removes it)"
    gone = []
    how = Removal(
        run=args.run, recheck=recheck, batch=args.batch, dry=not args.no_dry_run
    )
    for each, why in removals(how, chosen):
        gone.extend([] if why else [each])
        print(stuck_line(each, why) if why else removed_line(each, verb))
    return gone


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What a run of ``clean-container`` did.

    Attributes:
        gone: the paths removed (or, in a dry run, that would be).
        kept: the dead paths that are not safe.
        refused: the paths named that are no safe dead path now.
        removing: whether this was not a dry run.
        before: the bytes free before.
        after: the bytes free after.
    """

    gone: Sequence[dead.Candidate]
    kept: Sequence[dead.Candidate]
    refused: Sequence[pathlib.Path]
    removing: bool
    before: int
    after: int


def closing_lines(done: Outcome) -> Sequence[str]:
    """The lines after the removals: refusals, kept paths, totals, free space.

    Args:
        done: what the run did.

    Returns:
        The lines.
    """
    note = "(not a safe dead path directly in a configured root)"
    total = disk.size_text(sum(each.size for each in done.gone))
    held = disk.size_text(sum(each.size for each in done.kept))
    verb = "freed" if done.removing else "would be freed"
    return [
        *(
            f"{Marker.COULD_NOT_REMOVE_PATH.text} {path} {note}"
            for path in done.refused
        ),
        *(kept_line(each) for each in done.kept),
        f"container: {len(done.gone)} paths, {total} {verb};"
        f" {len(done.kept)} kept, {held}",
        f"disk: {disk.size_text(done.before)} free before,"
        f" {disk.size_text(done.after)} after",
    ]

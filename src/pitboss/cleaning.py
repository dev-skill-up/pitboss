"""What ``clean-container`` does with the dead paths: choose, remove in parts, say."""

import argparse
import contextlib
import dataclasses
import itertools
import pathlib
import subprocess
from typing import AbstractSet, Iterator, Sequence

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


def removals(
    run: Run, paths: Sequence[dead.Candidate], batch: int, dry: bool
) -> Iterator[tuple[dead.Candidate, bool]]:
    """Remove paths with one ``rm -rf`` for each part of at most ``batch``.

    Args:
        run: the runner for changes.
        paths: the candidates.
        batch: the most paths in one call.
        dry: whether the runner does nothing.

    Yields:
        Each candidate, and whether it is gone (as a dry run would leave it).
    """
    for part in itertools.batched(paths, batch):
        with contextlib.suppress(subprocess.CalledProcessError):
            run(["rm", "-rf", "--", *(str(each.path) for each in part)])
        for each in part:
            yield each, dry or not each.path.exists()


def prune(run: Run, gone: Sequence[dead.Candidate]) -> None:
    """Prune the worktree lists that a removed linked worktree was in.

    Args:
        run: the runner for changes.
        gone: the removed candidates.
    """
    for directory in sorted({each.prune for each in gone if each.prune}, key=str):
        git(run, directory, "worktree", "prune")


def choose(
    listed: Sequence[dead.Candidate], approved: AbstractSet[pathlib.Path] | None
) -> tuple[Sequence[dead.Candidate], Sequence[pathlib.Path]]:
    """The safe candidates to remove, and the approved paths that are not.

    Args:
        listed: the dead paths.
        approved: the paths approved, or None for every safe one.

    Returns:
        The candidates to remove and the approved paths that are no safe
        dead path now.
    """
    safe = dead.safe(listed)
    if approved is None:
        return safe, []
    chosen = [each for each in safe if each.path in approved]
    return chosen, sorted(approved - {each.path for each in chosen})


def kept_line(each: dead.Candidate) -> str:
    """The line for a dead path that is kept.

    Args:
        each: the candidate.

    Returns:
        The line.
    """
    return (
        f"{Marker.KEPT_PATH.text} {each.path} {disk.size_text(each.size)}"
        f" ({each.reason}): {each.kept}"
    )


def removed_line(each: dead.Candidate, verb: str) -> str:
    """The line for a path that was removed.

    Args:
        each: the candidate.
        verb: the dry run note, or empty.

    Returns:
        The line.
    """
    size = disk.size_text(each.size)
    return f"{Marker.REMOVED_PATH.text} {each.path} {size} ({each.reason}){verb}"


def stuck_line(each: dead.Candidate) -> str:
    """The line for a path that is still there after its ``rm``.

    Args:
        each: the candidate.

    Returns:
        The line.
    """
    size = disk.size_text(each.size)
    return f"{Marker.COULD_NOT_REMOVE_PATH.text} {each.path} {size} ({each.reason})"


def remove_all(
    args: argparse.Namespace, chosen: Sequence[dead.Candidate]
) -> Sequence[dead.Candidate]:
    """Remove the chosen paths in parts, saying what happened to each.

    Args:
        args: the parsed arguments.
        chosen: the safe paths to remove.

    Returns:
        The paths that are gone (all of them in a dry run).
    """
    verb = "" if args.no_dry_run else " (dry run: --no-dry-run removes it)"
    gone = []
    for each, removed in removals(args.run, chosen, args.batch, not args.no_dry_run):
        gone.extend([each] if removed else [])
        print(removed_line(each, verb) if removed else stuck_line(each))
    return gone


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What a run of ``clean-container`` did.

    Attributes:
        gone: the paths removed (or, in a dry run, that would be).
        kept: the dead paths that are not safe.
        refused: the approved paths that are no safe dead path now.
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
    note = "(not a safe dead path now)"
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

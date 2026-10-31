"""The cleaning a sweep does first, by itself, and harder when the disk is full.

Keyword: auto-clean (pitboss#120; the rule is in ``rules.md``, "Checkouts and
disk"). No prompt and no dry-run default: a sweep removes the test tempdirs
older than ``[clean] tmp_hours`` that the session user owns, the finished
worktrees and the dead checkouts, and prints what it removed and the space
freed. At or over ``[clean] pressure_percent`` of a filesystem used (90 by
default) it also removes tempdirs of a shorter age, every worktree and every
checkout of a repository without an open PR, and the package caches that
regenerate. It never touches a worktree with an open PR, a running worker's
directory (changed within ``idle_hours``, or marked ``.pitboss-live``), the
main clone or the directory it runs in, and it says so.
"""

import contextlib
import dataclasses
import datetime
import fnmatch
import functools
import operator
import os
import pathlib
import shutil
import subprocess
from typing import AbstractSet, Callable, Protocol, Sequence

from . import cleaning, cleanconfig, dead, deadscan, disk, mounts, survey, worktrees
from .running import Run

CACHES_IN_HOME = (
    ".cache/pip",
    ".cache/uv",
    ".cache/pre-commit",
    ".npm/_cacache",
    ".cargo/registry/cache",
)
BATCH = cleaning.DEFAULT_BATCH


class Filesystem(Protocol):
    """What the cleaning asks of the file system; tests pass a fake."""

    def children(self, directory: pathlib.Path) -> Sequence[pathlib.Path]:
        """List a directory.

        Args:
            directory: the directory.

        Returns:
            Its entries, sorted; none when it is not there.
        """

    def exists(self, path: pathlib.Path) -> bool:
        """Say whether something is at a path (a link counts as itself).

        Args:
            path: the path.

        Returns:
            True when there is.
        """

    def is_link(self, path: pathlib.Path) -> bool:
        """Say whether a path is a symbolic link.

        Args:
            path: the path.

        Returns:
            True when it is.
        """

    def owner(self, path: pathlib.Path) -> int:
        """Say who owns a path (a link is not followed).

        Args:
            path: the path.

        Returns:
            The user id.
        """

    def inspect(self, path: pathlib.Path) -> survey.Survey:
        """Walk a path once.

        Args:
            path: the path.

        Returns:
            Its size, its newest change, its marker and its mount points.
        """

    def remove(self, paths: Sequence[pathlib.Path]) -> None:
        """Remove paths, staying on one file system; a failure leaves them.

        Args:
            paths: the paths.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Real:
    """The file system of this machine; ``rm`` goes through the runner.

    Attributes:
        run: the runner for changes.
    """

    run: Run

    def children(self, directory: pathlib.Path) -> Sequence[pathlib.Path]:
        """List a directory.

        Args:
            directory: the directory.

        Returns:
            Its entries, sorted; none when it is not there.
        """
        try:
            return sorted(directory.iterdir())
        except OSError:
            return []

    def exists(self, path: pathlib.Path) -> bool:
        """Say whether something is at a path.

        Args:
            path: the path.

        Returns:
            True when there is.
        """
        return os.path.lexists(path)

    def is_link(self, path: pathlib.Path) -> bool:
        """Say whether a path is a symbolic link.

        Args:
            path: the path.

        Returns:
            True when it is.
        """
        return path.is_symlink()

    def owner(self, path: pathlib.Path) -> int:
        """Say who owns a path.

        Args:
            path: the path.

        Returns:
            The user id.
        """
        return path.lstat().st_uid

    def inspect(self, path: pathlib.Path) -> survey.Survey:
        """Walk a path once.

        Args:
            path: the path.

        Returns:
            What is in it.
        """
        return survey.walk(path, mounts.current())

    def remove(self, paths: Sequence[pathlib.Path]) -> None:
        """Remove paths with ``rm -rf --one-file-system``.

        Args:
            paths: the paths.
        """
        with contextlib.suppress(subprocess.CalledProcessError):
            self.run(["rm", "-rf", "--one-file-system", "--", *map(str, paths)])


def read_usage(path: pathlib.Path) -> disk.Usage | None:
    """Read the use of the file system of a path.

    Args:
        path: a path on it.

    Returns:
        The use, or None when the path is not there.
    """
    try:
        return disk.Usage(*shutil.disk_usage(path))
    except OSError:
        return None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Machine:
    """What the cleaning reads from the machine, all of it injected.

    Attributes:
        fs: the file system.
        usage: reads the use of a path's file system, None when absent.
        now: the time now.
        uid: the user whose tempdirs are removed.
        home: the home directory, where the package caches are.
        working: the directories the command runs in; never removed.
    """

    fs: Filesystem
    usage: Callable[[pathlib.Path], disk.Usage | None]
    now: datetime.datetime
    uid: int
    home: pathlib.Path
    working: AbstractSet[pathlib.Path] = frozenset()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Crowded:
    """A file system used up to the pressure.

    Attributes:
        path: a configured path on it.
        percent: how much of it is used.
    """

    path: pathlib.Path
    percent: float


def percent_used(usage: disk.Usage) -> float:
    """How much of a file system is used, as ``df`` counts it.

    Args:
        usage: its use.

    Returns:
        The percent; 0 for a file system of no size.
    """
    return 100 * (usage.total - usage.free) / usage.total if usage.total else 0.0


def crowded(
    machine: Machine, paths: Sequence[pathlib.Path], limit: float
) -> Sequence[Crowded]:
    """The file systems used up to the limit, each once.

    Args:
        machine: the machine.
        paths: the configured paths; one that is not there is left out.
        limit: the percent from which a file system is crowded.

    Returns:
        One entry for each, named by its first path.
    """
    seen: set[disk.Usage] = set()
    found = []
    for path in paths:
        usage = machine.usage(path)
        if usage is None or usage in seen:
            continue
        seen.add(usage)
        if percent_used(usage) >= limit:
            found.append(Crowded(path=path, percent=percent_used(usage)))
    return found


def holds_working(machine: Machine, path: pathlib.Path) -> bool:
    """Whether a path is, or lies above, a directory the command runs in.

    Args:
        machine: the machine.
        path: the path.

    Returns:
        True when removing it would remove the command's own directory.
    """
    return any(each == path or each.is_relative_to(path) for each in machine.working)


def stale_tempdirs(
    machine: Machine, clean: cleanconfig.Clean, hours: float
) -> Sequence[dead.Candidate]:
    """The tempdirs of the session user that nobody has touched for a while.

    A symbolic link, a path of another user, a path marked ``.pitboss-live``,
    one with a mount point in it and one that holds the directory the command
    runs in are left alone.

    Args:
        machine: the machine.
        clean: the settings.
        hours: how long a tempdir must be untouched.

    Returns:
        The candidates, largest first.
    """
    cutoff = machine.now.timestamp() - hours * 3600
    reason = f"test tempdir untouched for {hours:g} hours"
    found = []
    for root in clean.tmp_roots:
        for path in machine.fs.children(root):
            named = any(
                fnmatch.fnmatchcase(path.name, one) for one in clean.tmp_patterns
            )
            mine = named and not machine.fs.is_link(path)
            if not mine or machine.fs.owner(path) != machine.uid:
                continue
            if holds_working(machine, path):
                continue
            seen = machine.fs.inspect(path)
            if seen.marked or seen.mounts or seen.newest > cutoff:
                continue
            found.append(dead.Candidate(path=path, size=seen.size, reason=reason))
    return dead.ordered(found)


def regenerable_caches(
    machine: Machine, clean: cleanconfig.Clean
) -> Sequence[dead.Candidate]:
    """The package caches that regenerate: pip's, uv's, npm's and the configured.

    Args:
        machine: the machine.
        clean: the settings.

    Returns:
        The candidates, largest first; a cache that is a link, another user's,
        marked live or holding a mount point or the command's directory is left.
    """
    paths = [*(machine.home / name for name in CACHES_IN_HOME), *clean.caches]
    found = []
    for path in paths:
        if not machine.fs.exists(path) or machine.fs.is_link(path):
            continue
        seen = machine.fs.inspect(path)
        if machine.fs.owner(path) != machine.uid or seen.marked or seen.mounts:
            continue
        if holds_working(machine, path):
            continue
        found.append(
            dead.Candidate(
                path=path, size=seen.size, reason="package cache, regenerates"
            )
        )
    return dead.ordered(found)


def remove_found(
    machine: Machine, found: Sequence[dead.Candidate], dry: bool
) -> tuple[Sequence[str], Sequence[dead.Candidate]]:
    """Remove paths in parts, saying what happened to each.

    Args:
        machine: the machine.
        found: the paths.
        dry: whether to remove nothing.

    Returns:
        The lines, and the paths that are gone (all of them in a dry run).
    """
    note = " (dry run)" if dry else ""
    lines = []
    gone = []
    for part in _parts(found):
        if not dry:
            machine.fs.remove([each.path for each in part])
        for each in part:
            left = not dry and machine.fs.exists(each.path)
            gone.extend([] if left else [each])
            lines.append(
                cleaning.stuck_line(each, "rm left it in place")
                if left
                else cleaning.removed_line(each, note)
            )
    return lines, gone


def _parts(found: Sequence[dead.Candidate]) -> Sequence[Sequence[dead.Candidate]]:
    return [found[at : at + BATCH] for at in range(0, len(found), BATCH)]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Option:
    """How a run cleans.

    Attributes:
        run: the runner for changes (``rm`` and ``git worktree remove``).
        dry: whether to remove nothing.
        list_only: whether the finished worktrees are only listed, and the
            dead checkouts left, unless the disk is under pressure.
    """

    run: Run
    dry: bool
    list_only: bool = False


def paths_watched(look: dead.Look) -> Sequence[pathlib.Path]:
    """The paths whose file systems are watched for pressure.

    Args:
        look: what to look at and keep.

    Returns:
        The workspace, the tempdir roots and the scratch directories.
    """
    return [look.settings.project.workspace, *look.clean.tmp_roots, *look.clean.scratch]


def roots(look: dead.Look) -> AbstractSet[pathlib.Path]:
    """The directories whose entries may be removed.

    Args:
        look: what to look at and keep.

    Returns:
        The workspace, the scratch directories and the root of the files.
    """
    return {look.settings.project.workspace, *look.clean.scratch, look.watch.root}


def header(hot: Sequence[Crowded], clean: cleanconfig.Clean) -> str:
    """The line that says which cleaning this is.

    Args:
        hot: the crowded file systems.
        clean: the settings.

    Returns:
        The line.
    """
    limit = f"{clean.pressure_percent:g}%"
    if not hot:
        age = f"{clean.tmp_hours:g} hours"
        return (
            f"clean: disk under {limit} used: test tempdirs untouched for {age},"
            " finished worktrees and checkouts"
        )
    where = ", ".join(f"{each.path} {each.percent:.0f}%" for each in hot)
    age = f"{clean.pressure_tmp_hours:g} hours"
    return (
        f"clean: DISK OVER {limit} ({where}): aggressive: test tempdirs untouched"
        f" for {age}, every worktree and checkout without an open PR, package caches"
    )


def never_lines(look: dead.Look, aggressive: bool) -> Sequence[str]:
    """Say what the cleaning never touches; under pressure, name the worktrees.

    Args:
        look: what to look at and keep.
        aggressive: whether the disk is under pressure.

    Returns:
        The lines.
    """
    hours = look.settings.idle_hours
    kept = (
        "clean: never touched: a worktree with an open PR, a running worker's"
        f" directory (changed within {hours:g} hours or marked .pitboss-live),"
        " the main clone, the directory this command runs in"
    )
    named = [
        f"clean: kept {each.path} [{each.branch}] (open PR)"
        for each in (worktrees.tied_to_open_pr(look) if aggressive else [])
    ]
    return [*named, kept]


def checkouts_part(
    look: dead.Look, machine: Machine, option: Option, aggressive: bool
) -> tuple[Sequence[str], Sequence[dead.Candidate]]:
    """Remove the dead checkouts, scratch and root files that are safe.

    Args:
        look: what to look at and keep.
        machine: the machine.
        option: how to clean.
        aggressive: whether the disk is under pressure.

    Returns:
        The lines, and the paths that are gone.
    """
    now = machine.now.timestamp()
    found = deadscan.scan(look, now, aggressive)
    chosen, _ = cleaning.choose(found.candidates, None, roots(look))
    # The linked worktrees were judged above (git keeps one with untracked files);
    # only pressure takes them as dead paths too.
    chosen = [each for each in chosen if aggressive or each.prune is None]
    cutoff = now - look.settings.idle_hours * 3600
    how = cleaning.Removal(
        run=option.run,
        recheck=functools.partial(dead.recheck, look, cutoff),
        batch=BATCH,
        dry=option.dry,
    )
    note = " (dry run)" if option.dry else ""
    lines = [
        f"fetch failed in {name}: its checkouts are not judged"
        for name in found.unfetched
    ]
    gone = []
    for each, why in cleaning.removals(how, chosen):
        gone.extend([] if why else [each])
        lines.append(
            cleaning.stuck_line(each, why) if why else cleaning.removed_line(each, note)
        )
    cleaning.prune(option.run, gone)
    return lines, gone


def clean_lines(look: dead.Look, machine: Machine, option: Option) -> Sequence[str]:
    """Clean, and say what was removed and the space freed.

    Args:
        look: what to look at and keep.
        machine: the machine.
        option: how to clean.

    Returns:
        The lines: the mode, the worktrees, what was removed, what is never
        touched, and the totals.
    """
    clean = look.clean
    hot = crowded(machine, paths_watched(look), clean.pressure_percent)
    aggressive = bool(hot)
    workspace = look.settings.project.workspace
    before = machine.usage(workspace)
    lines = [header(hot, clean)]
    action = worktrees.Action(run=option.run, dry=option.dry)
    if option.list_only and not aggressive:
        lines += worktrees.stale_lines(look, machine.now)
    else:
        lines += worktrees.remove_lines(look, action, machine.now, aggressive)
    gone: list[dead.Candidate] = []
    if aggressive or not option.list_only:
        more, taken = checkouts_part(look, machine, option, aggressive)
        lines += more
        gone += taken
    hours = clean.pressure_tmp_hours if aggressive else clean.tmp_hours
    more, taken = remove_found(
        machine, stale_tempdirs(machine, clean, hours), option.dry
    )
    lines += more
    gone += taken
    if aggressive:
        more, taken = remove_found(
            machine, regenerable_caches(machine, clean), option.dry
        )
        lines += more
        gone += taken
    lines += never_lines(look, aggressive)
    lines.append(totals(gone, option.dry, before, machine.usage(workspace)))
    return lines


def totals(
    gone: Sequence[dead.Candidate],
    dry: bool,
    before: disk.Usage | None,
    after: disk.Usage | None,
) -> str:
    """The last line: how much was removed, and the free space around it.

    Args:
        gone: the paths removed (or, in a dry run, that would be).
        dry: whether nothing was removed.
        before: the use before.
        after: the use after.

    Returns:
        The line.
    """
    size = disk.size_text(sum(map(operator.attrgetter("size"), gone)))
    verb = "would be freed" if dry else "freed"
    return (
        f"clean: {len(gone)} paths removed, {size} {verb}; disk free"
        f" {free_text(before)} before, {free_text(after)} after"
    )


def free_text(usage: disk.Usage | None) -> str:
    """Spell the free space of a use.

    Args:
        usage: the use, or None when it could not be read.

    Returns:
        The size, or ``unknown``.
    """
    return disk.size_text(usage.free) if usage else "unknown"

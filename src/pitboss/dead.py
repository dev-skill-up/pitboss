"""Dead paths on this machine: what ``clean-container`` may remove, and why it may.

A path is dead when its work is finished (a checkout whose PR merged or closed,
or whose tip is in the base branch) or nobody uses it (scratch untouched for the
idle hours), and it is not live. A dead path is safe to remove when every git
checkout in it has its commits on a remote branch and no changed tracked file;
a dead path that is not safe is listed apart and never removed (keyword:
clean-container; the rule is in ``rules.md``, "Checkouts and disk").
"""

import dataclasses
import os
import pathlib
import subprocess
from typing import Iterable, Sequence

from . import cleanconfig, config, container, ghapi, local
from .running import Run, git

_BLOCK = 512


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Candidate:
    """A dead path.

    Attributes:
        path: the file or directory.
        size: the bytes it holds on disk.
        reason: why it is dead.
        kept: why it is not safe to remove, or empty when it is safe.
        prune: the git directory to prune after a linked worktree is removed.
    """

    path: pathlib.Path
    size: int
    reason: str
    kept: str = ""
    prune: pathlib.Path | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Look:
    """What looking at the machine needs.

    Attributes:
        run: the runner for reads.
        github: the API.
        settings: the configuration.
        clean: what ``clean-container`` looks at and keeps.
    """

    run: Run
    github: ghapi.GitHub
    settings: config.Config
    clean: cleanconfig.Clean


def _blocks(path: pathlib.Path) -> int:
    try:
        return path.lstat().st_blocks * _BLOCK
    except FileNotFoundError:
        return 0


def tree_size(path: pathlib.Path) -> int:
    """The bytes a path holds on disk (links are not followed).

    Args:
        path: a file or a directory.

    Returns:
        The size; 0 for a path that is gone.
    """
    total = _blocks(path)
    for directory, subdirectories, files in os.walk(path):
        total += sum(
            _blocks(pathlib.Path(directory) / name)
            for name in (*subdirectories, *files)
        )
    return total


def git_roots(path: pathlib.Path) -> Sequence[pathlib.Path]:
    """The git checkouts in a path: itself and those up to three levels down.

    Args:
        path: a directory.

    Returns:
        The directories that hold a ``.git``.
    """
    return [
        here
        for here, subdirectories, files in local.shallow_walk(path)
        if ".git" in subdirectories or ".git" in files
    ]


def trouble(run: Run, path: pathlib.Path) -> str:
    """Why a path is not safe to remove: work that exists only here.

    Args:
        run: the runner.
        path: the path.

    Returns:
        The reason, or empty when every checkout in it is on a remote branch
        with no changed tracked file.
    """
    for root in git_roots(path):
        try:
            top = git(run, root, "rev-parse", "--show-toplevel").strip()
            ahead = local.unpushed(run, root)
            changed = local.tracked_changes(run, root)
        except subprocess.CalledProcessError:
            top = ""
        if top == "" or pathlib.Path(top).resolve() != root.resolve():
            return f"git cannot read {root}"
        if ahead:
            return f"{ahead} commits on no remote branch in {root}"
        if changed:
            return f"{changed} changed tracked files in {root}"
    return ""


def is_live(path: pathlib.Path, look: Look) -> bool:
    """Whether a path is marked live, holds a live path or lies in one.

    Args:
        path: the path.
        look: what to keep: the main clone is always live.

    Returns:
        True when it must not be removed.
    """
    here = path.resolve()
    held = [here / cleanconfig.LIVE_MARKER, look.settings.project.main_clone.resolve()]
    held.extend(each.resolve() for each in look.clean.live)
    return held[0].exists() or any(
        here == each or here in each.parents or each in here.parents
        for each in held[1:]
    )


def touched(path: pathlib.Path, cutoff: float) -> bool:
    """Whether a file, or anything near the top of a directory, is newer than a time.

    Args:
        path: the path.
        cutoff: seconds since the epoch.

    Returns:
        True when it was touched after the cutoff.
    """
    if path.is_dir():
        return local.touched_since(path, cutoff)
    return path.lstat().st_mtime > cutoff


def dead_root_files(
    marker: pathlib.Path, root: pathlib.Path, hours: float
) -> Sequence[Candidate]:
    """The files in a container's root written well after it started.

    Args:
        marker: the file the container started with; absent, there are none.
        root: the directory.
        hours: how long after the marker a file must be written.

    Returns:
        The candidates.
    """
    if not marker.exists():
        return []
    after = container.cutoff(marker, hours)
    reason = f"written over {hours:g} hours after the container started"
    return [
        Candidate(path=each.path, size=each.size, reason=reason)
        for each in container.newer_files(root, after)
    ]


def safe(found: Iterable[Candidate]) -> Sequence[Candidate]:
    """The candidates that are safe to remove.

    Args:
        found: the candidates.

    Returns:
        Those with nothing in them that exists only on this machine.
    """
    return [each for each in found if not each.kept]


def unsafe(found: Iterable[Candidate]) -> Sequence[Candidate]:
    """The candidates that are kept: some work in them exists only here.

    Args:
        found: the candidates.

    Returns:
        Those with a reason not to remove them.
    """
    return [each for each in found if each.kept]


def ordered(found: Iterable[Candidate]) -> Sequence[Candidate]:
    """Largest first, each path once.

    Args:
        found: the candidates.

    Returns:
        The candidates in the order they are listed.
    """
    unique = {each.path: each for each in found}
    return sorted(unique.values(), key=lambda each: (-each.size, str(each.path)))


def make(
    run: Run, path: pathlib.Path, reason: str, prune: pathlib.Path | None = None
) -> Candidate:
    """Measure a dead path and check that it is safe.

    Args:
        run: the runner for reads.
        path: the path.
        reason: why it is dead.
        prune: the git directory to prune after a linked worktree goes.

    Returns:
        The candidate.
    """
    return Candidate(
        path=path,
        size=tree_size(path),
        reason=reason,
        kept=trouble(run, path),
        prune=prune,
    )


def dead_scratch(look: Look, cutoff: float) -> Sequence[Candidate]:
    """The entries of the scratch directories that nobody uses.

    Args:
        look: what to look at and keep.
        cutoff: anything touched after this time is in use.

    Returns:
        The candidates.
    """
    hours = look.settings.idle_hours
    reason = f"unreferenced scratch, untouched for {hours:g} hours"
    entries = (
        entry
        for root in look.clean.scratch
        if root.is_dir()
        for entry in sorted(root.iterdir())
        if not entry.is_symlink()
    )
    return [
        make(look.run, entry, reason)
        for entry in entries
        if not is_live(entry, look) and not touched(entry, cutoff)
    ]

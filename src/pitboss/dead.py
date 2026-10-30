"""Dead paths on this machine: what ``clean-container`` may remove, and why it may.

A path is dead when its work is finished (a checkout whose PR merged or closed,
or whose tip is in the base branch) or nobody uses it (scratch untouched for the
idle hours), and it is not live. A dead path is safe to remove when everything
in it exists elsewhere (``repocheck``); a dead path that is not safe is listed
apart and never removed (keyword: clean-container; the rule is in ``rules.md``,
"Checkouts and disk"). Every check looks at the whole tree of the path
(``survey``) and is made again just before the removal.
"""

import dataclasses
import os
import pathlib
from typing import AbstractSet, Callable, Iterable, Sequence

from . import cleanconfig, config, container, ghapi, mounts, repocheck, survey
from .running import Run


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
        watch: where the session's own files in the root are.
        mount_points: reads the mount points of the machine.
        working: the directories the command runs in; a path that is or holds
            one is in use (keyword: clean-worktrees).
    """

    run: Run
    github: ghapi.GitHub
    settings: config.Config
    clean: cleanconfig.Clean
    watch: container.Watch = container.WATCH
    mount_points: Callable[[], AbstractSet[pathlib.Path]] = mounts.current
    working: AbstractSet[pathlib.Path] = frozenset()


def marked_above(path: pathlib.Path) -> bool:
    """Whether a directory above a path holds a live marker.

    Args:
        path: the path.

    Returns:
        True when any of its parents does.
    """
    return any(
        os.path.lexists(above / cleanconfig.LIVE_MARKER)
        for above in path.resolve().parents
    )


def on_live_path(path: pathlib.Path, look: Look) -> bool:
    """Whether a path is the main clone or a live path, or holds or lies in one.

    Args:
        path: the path.
        look: what to keep.

    Returns:
        True when it must not be removed.
    """
    here = path.resolve()
    held = [look.settings.project.main_clone, *look.clean.live]
    return any(
        here == each or here in each.parents or each in here.parents
        for each in (one.resolve() for one in held)
    )


def live_reason(path: pathlib.Path, look: Look, found: survey.Survey) -> str:
    """Why a path is live: marked, holding or lying in a marked or kept path.

    Args:
        path: the path.
        look: what to keep.
        found: what a walk of the path found.

    Returns:
        The reason, or empty when it is not live.
    """
    if found.marked:
        return "holds a file named .pitboss-live"
    if marked_above(path):
        return "lies under a directory that holds a .pitboss-live file"
    if on_live_path(path, look):
        return "is, holds or lies in a live path"
    return ""


def runs_in(path: pathlib.Path, look: Look) -> bool:
    """Whether a path is, or lies above, a directory the command runs in.

    Args:
        path: the path.
        look: what to keep.

    Returns:
        True when removing it would remove the command's own directory.
    """
    here = path.resolve()
    return any(each.resolve().is_relative_to(here) for each in look.working)


def hold(look: Look, path: pathlib.Path, cutoff: float) -> tuple[str, survey.Survey]:
    """Look at a path and say whether it must be left alone: live or in use.

    Args:
        look: what to look at and keep.
        path: the path.
        cutoff: anything changed after this time is in use.

    Returns:
        The reason to leave it alone, or empty, and what a walk of it found.
    """
    found = survey.walk(path, look.mount_points())
    reasons = (
        "is a symbolic link" if path.is_symlink() else "",
        live_reason(path, look, found),
        "is or holds the directory this command runs in" if runs_in(path, look) else "",
        "changed within the idle hours" if found.newest > cutoff else "",
    )
    return next((reason for reason in reasons if reason), ""), found


def verdict(
    look: Look, path: pathlib.Path, cutoff: float
) -> tuple[str, str, survey.Survey]:
    """The one safety test: is a path live or in use, and is work only in it.

    ``consider``, ``recheck`` and the removal of finished worktrees all ask this
    (keyword: clean-container, clean-worktrees).

    Args:
        look: what to look at and keep.
        path: the path.
        cutoff: anything changed after this time is in use.

    Returns:
        Why the path is live or in use (empty when it is not), why it is not
        safe to remove (empty when it is; not asked of a held path), and what a
        walk of it found.
    """
    held, found = hold(look, path, cutoff)
    kept = "" if held else repocheck.trouble(look.run, path, found)
    return held, kept, found


def consider(
    look: Look, path: pathlib.Path, reason: str, cutoff: float
) -> Candidate | None:
    """Measure a dead path and check that it is safe.

    Args:
        look: what to look at and keep.
        path: the path.
        reason: why it is dead.
        cutoff: anything changed after this time is in use.

    Returns:
        The candidate, or None when the path is live or in use.
    """
    held, kept, found = verdict(look, path, cutoff)
    if held:
        return None
    return Candidate(path=path, size=found.size, reason=reason, kept=kept)


def recheck(look: Look, cutoff: float, each: Candidate) -> str:
    """Look again, just before the removal, at a path that was listed.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.
        each: the candidate.

    Returns:
        Why the path must not be removed now, or empty when it may (a path
        that is already gone may).
    """
    if not os.path.lexists(each.path):
        return ""
    held, kept, _ = verdict(look, each.path, cutoff)
    return held or kept


def present(made: Iterable[Candidate | None]) -> Sequence[Candidate]:
    """The candidates among what was considered.

    Args:
        made: each path considered, as a candidate or None.

    Returns:
        The candidates.
    """
    return [each for each in made if each is not None]


def dead_root_files(look: Look, cutoff: float) -> Sequence[Candidate]:
    """The files in a container's root written well after it started.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.

    Returns:
        The candidates; none when the marker file is absent.
    """
    watch = look.watch
    if not watch.marker.exists():
        return []
    after = container.cutoff(watch.marker, watch.hours)
    reason = f"written over {watch.hours:g} hours after the container started"
    files = container.newer_files(watch.root, after)
    return present(consider(look, each.path, reason, cutoff) for each in files)


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


def dead_scratch(look: Look, cutoff: float) -> Sequence[Candidate]:
    """The entries of the scratch directories that nobody uses.

    Args:
        look: what to look at and keep.
        cutoff: anything changed after this time is in use.

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
    )
    return present(consider(look, entry, reason, cutoff) for entry in entries)

"""A merged ticket's worktree goes with the merge (keyword: merge-removes-worktree).

The worktree of pitboss#469 stayed on disk after its merge, 295 MB, at 5.2 GiB
free, under ``pitboss nox``'s floor of 5.0 GiB, because its ``.pitboss-live``
marker kept it for hours (pitboss#471). ``pitboss merged`` removes the worktree of
a merged PR at once: the marker of a worker whose PR merged is dropped, and the
worktree goes with ``git worktree remove`` and no ``--force``, only when it is
clean. ``slots next`` lists every worktree whose PR merged or closed as a removal
step with its size.
"""

import dataclasses
import datetime
import pathlib
import subprocess
from typing import Sequence

from . import dead, disk, judging, local, survey, untracked, worktrees
from .markers import Marker
from .running import Run, git

REMOVE = "REMOVE WORKTREE"


def _unmarked(look: dead.Look, path: pathlib.Path) -> dead.Look:
    return dataclasses.replace(look, unmarked=frozenset({path.resolve()}))


def _why_kept(
    look: dead.Look, path: pathlib.Path, now: datetime.datetime
) -> tuple[str, int]:
    idle = now.timestamp() - look.settings.idle_hours * 3600
    held, kept, found = dead.verdict(look, path, idle)
    return held or kept or untracked.files_but_marker(look.run, path), found.size


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Removal:
    """How a merged branch's worktrees are removed.

    Attributes:
        look: what to look at and keep.
        run: the runner for changes.
        now: the time now.
        dry: whether the runner does nothing.
    """

    look: dead.Look
    run: Run
    now: datetime.datetime
    dry: bool


def _remove_one(how: Removal, each: judging.Finished) -> tuple[str, int]:
    # the line, and the bytes freed
    path = each.worktree.path
    why, size = _why_kept(_unmarked(how.look, path), path, how.now)
    if why:
        return f"{Marker.KEPT_WORKTREE.text} {path} ({why})", 0
    main_clone = how.look.settings.project.main_clone
    try:
        if not how.dry:
            (path / survey.LIVE_MARKER).unlink(missing_ok=True)
        git(how.run, main_clone, "worktree", "remove", str(path))
    except (subprocess.CalledProcessError, OSError):  # pragma: no cover
        return f"{Marker.COULD_NOT_REMOVE_WORKTREE.text} {path}", 0
    note = " (dry run: --no-dry-run removes it)" if how.dry else ""
    return (
        f"{Marker.REMOVED_WORKTREE.text} {path} (merged): freed {size} bytes{note}",
        size,
    )


def remove(how: Removal, branch: str) -> Sequence[str]:
    """Remove the worktrees of a merged branch that are clean.

    Args:
        how: how to remove them.
        branch: the branch of the merged PR.

    Returns:
        A line for each worktree, with the bytes freed, then the total.
    """
    found = [
        each
        for each in worktrees.find(how.look)
        if each.worktree.branch == branch and each.reason in local.MERGED_WORK
    ]
    done = [_remove_one(how, each) for each in found]
    freed = sum(size for _, size in done)
    return [
        *(line for line, _ in done),
        f"worktrees: {len(done)} listed, freed {freed} bytes",
    ]


def steps(look: dead.Look, now: datetime.datetime) -> Sequence[str]:
    """The removal steps of the worktrees whose PR merged or closed.

    Args:
        look: what to look at and keep.
        now: the time now.

    Returns:
        A ``REMOVE WORKTREE`` line for each, with its size and the command; none
        when the PRs cannot be read.
    """
    try:
        done = worktrees.find(look)
    except (subprocess.CalledProcessError, OSError):  # pragma: no cover
        return []
    lines = []
    for each in done:
        path = each.worktree.path
        size = disk.size_text(_why_kept(_unmarked(look, path), path, now)[1])
        lines.append(
            f"{REMOVE} {path} ({size}, {each.reason.value}): run"
            f" `pitboss merged --no-dry-run {each.worktree.branch}`"
        )
    return lines

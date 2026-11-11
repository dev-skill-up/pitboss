"""The merge step removes the merged ticket's worktree and lists the others.

(Keyword: merge-step, pitboss#471.) The worktree of pitboss#469 stayed after its
merge, at 5.2 GiB free, below the floor of ``pitboss nox``: the one whose PR merged
last keeps its ``.pitboss-live`` marker under pressure. ``slots next``, which the
orchestrator runs after each merge, so removes the worktree of every merged PR
that is clean, with ``git worktree remove`` and no ``--force`` (the marker, which
belongs to a worker that is done, is deleted first), and prints the bytes freed.
Each worktree whose PR is merged or closed and that is still there is a
``STALE WORKTREE`` line with its size, why it stays and the command that removes
it.
"""

import datetime
import pathlib
import subprocess
from typing import Sequence

from . import cleanconfig, disk, judging, local, worktrees
from .dead import Look
from .markers import Marker
from .running import Run, git


def _judged(
    look: Look, now: datetime.datetime, each: judging.Finished
) -> judging.Judged:
    # a merged work's marker is not honored: its worker is done
    pressure = judging.Pressure(last=None) if each.reason in local.MERGED_WORK else None
    return worktrees.judge(look, now, each, pressure)


def _removed(run: Run, look: Look, judged: judging.Judged) -> bool:
    # git worktree remove, never forced; the marker of a done worker goes first
    path = judged.found.worktree.path
    if judged.ignored:
        pathlib.Path(path, cleanconfig.LIVE_MARKER).unlink(missing_ok=True)
    try:
        git(run, look.settings.project.main_clone, "worktree", "remove", str(path))
    except subprocess.CalledProcessError:
        return False
    return True


def _step(judged: judging.Judged) -> str:
    # a worktree that stays: its size, why, and the command that removes it
    found = judged.found
    what = f"{found.reason.value}, {disk.size_text(judged.size)}"
    how = judged.why or "pitboss clean-worktrees --no-dry-run removes it"
    return (
        f"{Marker.STALE_WORKTREE.text} {found.worktree.path}"
        f" [{found.worktree.branch}] ({what}): {how}"
    )


def _outcome(
    look: Look, run: Run, now: datetime.datetime, each: judging.Finished
) -> tuple[str, int]:
    # the line about one finished worktree, and the bytes it freed
    judged = _judged(look, now, each)
    if (
        each.reason in local.MERGED_WORK
        and not judged.why
        and _removed(run, look, judged)
    ):
        said = (
            f"{Marker.REMOVED_WORKTREE.text} {each.worktree.path}"
            f" ({each.reason.value}, merge step): {disk.size_text(judged.size)}"
        )
        return said, judged.size
    return _step(judged), 0


def lines(look: Look, run: Run, now: datetime.datetime) -> Sequence[str]:
    """Remove the merged ticket's clean worktrees, and list the rest of the finished.

    Args:
        look: what to look at and keep.
        run: the runner for changes.
        now: the time now.

    Returns:
        A line for each worktree removed (with its size) and for each finished
        one that stays, then the bytes freed; none when no worktree is finished.
    """
    done = [_outcome(look, run, now, each) for each in worktrees.find(look)]
    freed = sum(size for _, size in done)
    removed = sum(
        1 for said, _ in done if said.startswith(Marker.REMOVED_WORKTREE.text)
    )
    total = f"worktrees: {removed} removed, {disk.size_text(freed)} freed"
    return [*(said for said, _ in done), total] if done else []


def report(look: Look, run: Run, now: datetime.datetime) -> None:
    """Print the lines of the merge step.

    Args:
        look: what to look at and keep.
        run: the runner for changes.
        now: the time now.
    """
    for each in lines(look, run, now):
        print(each)

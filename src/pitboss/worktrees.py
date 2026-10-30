"""Finished worktrees: found by their PR, kept or removed by the one safety test.

A worktree is finished when its PR merged or closed, or its tip is in the base
branch (``local.finished_reason``). Whether it may go is ``dead.verdict``, the
test ``clean-container`` and the ``DISK PRESSURE`` line use: not live, not in
use, and no commit on no remote branch and no changed tracked file in it
(keyword: clean-worktrees, ``rules.md``, "Checkouts and disk").
"""

import dataclasses
import datetime
import subprocess
from typing import Sequence

from . import dead, disk, local
from .markers import Marker
from .running import Run, git


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Finished:
    """A worktree whose work is finished and on GitHub.

    Attributes:
        worktree: the worktree.
        reason: why it is finished.
    """

    worktree: local.Worktree
    reason: local.Reason


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Judged:
    """A finished worktree and what the safety test said of it.

    Attributes:
        found: the finished worktree.
        size: the bytes it holds on disk.
        why: why it is not removed, or empty when it may be.
    """

    found: Finished
    size: int
    why: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Action:
    """How the finished worktrees are removed.

    Attributes:
        run: the runner for changes.
        dry: whether the runner does nothing.
    """

    run: Run
    dry: bool


def find(look: dead.Look) -> Sequence[Finished]:
    """Find the worktrees of the main clone whose work is finished.

    Args:
        look: what to look at and keep.

    Returns:
        The finished worktrees; whether each may go is ``judge``'s.
    """
    project = look.settings.project
    git(look.run, project.main_clone, "fetch", "-q", "origin", project.base_branch)
    sweeper = local.Sweeper(
        run=look.run,
        settings=look.settings,
        outcomes=local.read_outcomes(look.github, project.repo),
    )
    listed = git(look.run, project.main_clone, "worktree", "list", "--porcelain")
    decided = [
        (each, local.finished_reason(sweeper, each))
        for each in local.parse_worktrees(listed)
    ]
    return [
        Finished(worktree=each, reason=reason)
        for each, reason in decided
        if reason is not None
    ]


def judge(look: dead.Look, now: datetime.datetime, each: Finished) -> Judged:
    """Apply the safety test to one finished worktree.

    Args:
        look: what to look at and keep.
        now: the time now.
        each: the finished worktree.

    Returns:
        What the test said.
    """
    cutoff = now.timestamp() - look.settings.idle_hours * 3600
    held, kept, found = dead.verdict(look, each.worktree.path, cutoff)
    return Judged(found=each, size=found.size, why=held or kept)


def stale_lines(look: dead.Look, now: datetime.datetime) -> Sequence[str]:
    """The lines of a sweep under ``list``: the worktrees that may be removed.

    Args:
        look: what to look at and keep.
        now: the time now.

    Returns:
        A ``STALE WORKTREE`` line for each that passed the test, then the count.
    """
    done = [judge(look, now, each) for each in find(look)]
    safe = [each.found for each in done if not each.why]
    return [
        *(
            f"{Marker.STALE_WORKTREE.text} {each.worktree.path}"
            f" [{each.worktree.branch}] ({each.reason.value}):"
            " clean-worktrees removes it"
            for each in safe
        ),
        f"worktrees: {len(safe)} stale",
    ]


def kept_line(each: Judged) -> str:
    """The line for a finished worktree that is not removed.

    Args:
        each: the judgement.

    Returns:
        The line.
    """
    return f"{Marker.KEPT_WORKTREE.text} {each.found.worktree.path} ({each.why})"


def removal_line(action: Action, look: dead.Look, each: Judged) -> tuple[str, bool]:
    """Remove one worktree that passed the test, and say what happened.

    Args:
        action: how to remove it.
        look: what to look at and keep.
        each: the judgement.

    Returns:
        The line, and whether the worktree was removed.
    """
    path = each.found.worktree.path
    main_clone = look.settings.project.main_clone
    try:
        git(action.run, main_clone, "worktree", "remove", str(path))
    except subprocess.CalledProcessError:
        return f"{Marker.COULD_NOT_REMOVE_WORKTREE.text} {path}", False
    verb = " (dry run: --no-dry-run removes it)" if action.dry else ""
    said = f"{Marker.REMOVED_WORKTREE.text} {path} ({each.found.reason.value}){verb}"
    return said, True


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What happened to one finished worktree.

    Attributes:
        said: the line about it.
        freed: the bytes it held, when it was removed.
        kept: whether the safety test kept it.
        removed: whether it was removed.
    """

    said: str
    freed: int
    kept: bool
    removed: bool


def act(
    look: dead.Look, action: Action, moment: datetime.datetime, each: Finished
) -> Outcome:
    """Judge one finished worktree and, if it passes, remove it right away.

    Args:
        look: what to look at and keep.
        action: how to remove it.
        moment: the time now.
        each: the finished worktree.

    Returns:
        What happened.
    """
    made = judge(look, moment, each)
    if made.why:
        return Outcome(said=kept_line(made), freed=0, kept=True, removed=False)
    said, removed = removal_line(action, look, made)
    return Outcome(said=said, freed=made.size * removed, kept=False, removed=removed)


def remove_lines(
    look: dead.Look, action: Action, moment: datetime.datetime
) -> Sequence[str]:
    """Remove the finished worktrees that pass the safety test, saying what happened.

    Each is judged right before its removal, and the worktree lists are pruned
    last.

    Args:
        look: what to look at and keep.
        action: how to remove them.
        moment: the time now.

    Returns:
        A line for each worktree, then the totals.
    """
    steps = [act(look, action, moment, each) for each in find(look)]
    git(action.run, look.settings.project.main_clone, "worktree", "prune")
    freed = disk.size_text(sum(each.freed for each in steps))
    verb = "would be freed" if action.dry else "freed"
    removed = sum(each.removed for each in steps)
    kept = sum(each.kept for each in steps)
    total = f"worktrees: {removed} removed, {freed} {verb}; {kept} kept"
    return [*(each.said for each in steps), total]

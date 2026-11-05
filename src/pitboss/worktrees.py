"""Finished worktrees: found by their PR, kept or removed by the one safety test.

A worktree is finished when its PR merged or closed, or its tip is in the base
branch (``local.finished_reason``). Whether it may go is ``dead.verdict``, the
test ``clean-container`` and the ``DISK PRESSURE`` line use: not live, not in
use, and no commit on no remote branch and no changed tracked file in it
(keyword: clean-worktrees, ``rules.md``, "Checkouts and disk"). One that passes
but holds untracked files is kept too, since ``git worktree remove`` refuses it,
unless the marker ignored under pressure is the only untracked file, when it is
removed with ``--force``.
"""

import dataclasses
import datetime
import pathlib
import subprocess
from typing import AbstractSet, Callable, Sequence

from . import dead, disk, judging, local, mergetime, survey, untracked, workhours
from .judging import Finished, Judged, Pressure, at_ease
from .markers import Marker
from .running import Run, git

Decide = Callable[[local.Sweeper, local.Worktree], local.Reason | None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Action:
    """How the finished worktrees are removed.

    Attributes:
        run: the runner for changes.
        dry: whether the runner does nothing.
        weigh: ``under_pressure`` when the disk is crowded (the merged
            worktrees lose their markers but the one that merged last), else
            ``at_ease``.
        pressure: what ``weigh`` said of the finished worktrees; set by
            ``remove_lines``.
    """

    run: Run
    dry: bool
    weigh: Callable[[Sequence[Finished]], Pressure | None] = at_ease
    pressure: Pressure | None = None


def _listed(look: dead.Look) -> tuple[local.Sweeper, Sequence[local.Worktree]]:
    project = look.settings.project
    sweeper = local.Sweeper(
        run=look.run,
        settings=look.settings,
        outcomes=local.read_outcomes(look.github, project.repo),
    )
    return sweeper, _porcelain(look)


def _porcelain(look: dead.Look) -> Sequence[local.Worktree]:
    main_clone = look.settings.project.main_clone
    return local.parse_worktrees(
        git(look.run, main_clone, "worktree", "list", "--porcelain")
    )


def registered(look: dead.Look) -> AbstractSet[pathlib.Path]:
    """The paths of the worktrees registered in the main clone.

    Args:
        look: what to look at and keep.

    Returns:
        The paths, the main clone's own included.
    """
    return {each.path for each in _porcelain(look)}


def tied_to_open_pr(look: dead.Look) -> Sequence[local.Worktree]:
    """The worktrees of the main clone whose branch has an open PR.

    Cleaning never touches them, whatever the disk (keyword: auto-clean).

    Args:
        look: what to look at and keep.

    Returns:
        The worktrees.
    """
    sweeper, listed = _listed(look)
    return [
        each
        for each in listed
        if each.branch in sweeper.outcomes and sweeper.outcomes[each.branch].still_open
    ]


def find(look: dead.Look, decide: Decide = local.finished_reason) -> Sequence[Finished]:
    """Find the worktrees of the main clone whose work is finished.

    Args:
        look: what to look at and keep.
        decide: whether a worktree is finished: ``local.finished_reason``, or
            ``local.pressure_reason`` under disk pressure (keyword: auto-clean).

    Returns:
        The finished worktrees; whether each may go is ``judge``'s.
    """
    project = look.settings.project
    git(look.run, project.main_clone, "fetch", "-q", "origin", project.base_branch)
    sweeper, listed = _listed(look)
    pairs = [(each, decide(sweeper, each)) for each in listed]
    found = [(each, reason) for each, reason in pairs if reason is not None]
    return [
        Finished(
            worktree=each,
            reason=reason,
            merged=mergetime.merged_at(sweeper, each, reason),
        )
        for each, reason in found
    ]


def _forgiven(each: Finished, pressure: Pressure | None) -> bool:
    # Under pressure a merged worktree's marker is not honored, but the last's.
    merged = each.reason in local.MERGED_WORK
    return pressure is not None and merged and each != pressure.last


def _eyes(
    look: dead.Look, each: Finished, unmarked: AbstractSet[pathlib.Path]
) -> dead.Look:
    # Only a merged worktree's marker expires.
    expiry = look.marker_expiry if each.reason in local.MERGED_WORK else 0.0
    return dataclasses.replace(look, unmarked=unmarked, marker_expiry=expiry)


def _ignored(
    eyes: dead.Look, found: survey.Survey, forgiven: bool
) -> tuple[bool, bool]:
    # Whether the marker was not honored, and whether that was its age.
    stale = not forgiven and workhours.expired(eyes.marker_expiry, found)
    return found.marked and (forgiven or stale), stale


def judge(
    look: dead.Look,
    now: datetime.datetime,
    each: Finished,
    pressure: Pressure | None = None,
) -> Judged:
    """Apply the safety test to one finished worktree.

    Under disk pressure a merged worktree's own ``.pitboss-live`` marker is not
    honored, except on the one whose work merged last: a marker outlives its
    work. The marker of a merged worktree is not honored either, whatever the
    disk, once it is older than a worker's task. Keyword: auto-clean,
    ``workhours``, pitboss#194.

    Args:
        look: what to look at and keep.
        now: the time now.
        each: the finished worktree.
        pressure: what the pressure does to markers, or None when the disk has room.

    Returns:
        What the test said.
    """
    forgiven = _forgiven(each, pressure)
    path = each.worktree.path
    unmarked = frozenset({path.resolve()}) if forgiven else look.unmarked
    eyes = _eyes(look, each, unmarked)
    idle = now.timestamp() - look.settings.idle_hours * 3600
    held, kept, found = dead.verdict(eyes, path, idle)
    ignored, stale = _ignored(eyes, found, forgiven)
    refused = untracked.files_but_marker if ignored else untracked.files
    why = held or kept or refused(look.run, path)
    last = pressure is not None and each == pressure.last
    return Judged(
        found=each, size=found.size, why=why, ignored=ignored, stale=stale, last=last
    )


def stale_lines(
    look: dead.Look, now: datetime.datetime, decide: Decide = local.finished_reason
) -> Sequence[str]:
    """The lines of a sweep under ``list``: the worktrees that may be removed.

    Args:
        look: what to look at and keep.
        now: the time now.
        decide: whether a worktree is finished.

    Returns:
        A ``STALE WORKTREE`` line for each that passed the test, then the count.
    """
    done = [judge(look, now, each) for each in find(look, decide)]
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
    named = "; its PR merged last" if each.last and each.why == dead.MARKED else ""
    return f"{Marker.KEPT_WORKTREE.text} {each.found.worktree.path} ({each.why}{named})"


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
        forced = ("--force",) if each.ignored else ()
        git(action.run, main_clone, "worktree", "remove", *forced, str(path))
    except subprocess.CalledProcessError:
        return f"{Marker.COULD_NOT_REMOVE_WORKTREE.text} {path}", False
    verb = " (dry run: --no-dry-run removes it)" if action.dry else ""
    note = judging.marker_note(each)
    reason = f"{each.found.reason.value}{note}"
    return f"{Marker.REMOVED_WORKTREE.text} {path} ({reason}){verb}", True


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Outcome:
    """What happened to one finished worktree.

    Attributes:
        said: the line about it.
        freed: the bytes it held, when it was removed.
        kept: whether the safety test kept it.
        removed: whether it was removed.
        left: the directory, and why it is still there, when it is.
    """

    said: str
    freed: int
    kept: bool
    removed: bool
    left: dead.Kept | None = None


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Removed:
    """What removing the finished worktrees did.

    Attributes:
        lines: a line for each worktree, then the totals.
        freed: the bytes freed (or, in a dry run, that would be).
        left: the finished worktrees still on disk, each with why.
    """

    lines: Sequence[str]
    freed: int
    left: Sequence[dead.Kept]


def act(
    look: dead.Look,
    action: Action,
    moment: datetime.datetime,
    each: Finished,
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
    made = judge(look, moment, each, action.pressure)
    path = each.worktree.path
    if made.why:
        left = dead.Kept(path=path, why=made.why, size=made.size)
        return Outcome(
            said=kept_line(made), freed=0, kept=True, removed=False, left=left
        )
    said, removed = removal_line(action, look, made)
    stuck = None if removed else dead.Kept(path=path, why=said, size=made.size)
    return Outcome(
        said=said, freed=made.size * removed, kept=False, removed=removed, left=stuck
    )


def remove_lines(
    look: dead.Look,
    action: Action,
    moment: datetime.datetime,
    decide: Decide = local.finished_reason,
) -> Sequence[str]:
    """Remove the finished worktrees that pass the safety test, saying what happened.

    Args:
        look: what to look at and keep.
        action: how to remove them.
        moment: the time now.
        decide: whether a worktree is finished.

    Returns:
        A line for each worktree, then the totals.
    """
    return removal(look, action, moment, decide).lines


def removal(
    look: dead.Look,
    action: Action,
    moment: datetime.datetime,
    decide: Decide = local.finished_reason,
) -> Removed:
    """Remove the finished worktrees that pass the safety test, saying what happened.

    Each is judged right before its removal, and the worktree lists are pruned
    last.

    Args:
        look: what to look at and keep.
        action: how to remove them.
        moment: the time now.
        decide: whether a worktree is finished.

    Returns:
        The lines, the bytes freed and the worktrees left.
    """
    found = find(look, decide)
    weighed = dataclasses.replace(action, pressure=action.weigh(found))
    steps = [act(look, weighed, moment, each) for each in found]
    git(action.run, look.settings.project.main_clone, "worktree", "prune")
    freed = sum(each.freed for each in steps)
    verb = "would be freed" if action.dry else "freed"
    removed = sum(each.removed for each in steps)
    kept = sum(each.kept for each in steps)
    total = f"worktrees: {removed} removed, {disk.size_text(freed)} {verb}; {kept} kept"
    return Removed(
        lines=[*(each.said for each in steps), total],
        freed=freed,
        left=[each.left for each in steps if each.left is not None],
    )

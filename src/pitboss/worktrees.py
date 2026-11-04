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
import subprocess
from typing import Callable, Sequence

from . import dead, disk, local, mergetime, untracked
from .markers import Marker
from .running import Run, git

Decide = Callable[[local.Sweeper, local.Worktree], local.Reason | None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Finished:
    """A worktree whose work is finished and on GitHub.

    Attributes:
        worktree: the worktree.
        reason: why it is finished.
        merged: when it merged, in seconds (the PR's merge, or the tip's commit
            when it has no PR), or 0 when it did not merge.
    """

    worktree: local.Worktree
    reason: local.Reason
    merged: float = 0.0


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pressure:
    """What disk pressure does to the live markers of the merged worktrees.

    Attributes:
        last: the merged worktree that merged last, or None when none merged;
            it keeps its marker (keyword: auto-clean).
    """

    last: Finished | None


def at_ease(found: Sequence[Finished]) -> Pressure | None:
    """What the disk does to markers when it has room: nothing.

    Args:
        found: the finished worktrees.

    Returns:
        None.
    """
    return None


def under_pressure(found: Sequence[Finished]) -> Pressure | None:
    """What a crowded disk does to markers: the last merged worktree keeps its own.

    Args:
        found: the finished worktrees.

    Returns:
        The pressure.
    """
    return Pressure(last=last_merged(found))


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Judged:
    """A finished worktree and what the safety test said of it.

    Attributes:
        found: the finished worktree.
        size: the bytes it holds on disk.
        why: why it is not removed, or empty when it may be.
        ignored: whether its ``.pitboss-live`` marker was not honored.
        last: whether it is the merged worktree that merged last, under pressure.
    """

    found: Finished
    size: int
    why: str
    ignored: bool = False
    last: bool = False


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
    listed = git(look.run, project.main_clone, "worktree", "list", "--porcelain")
    return sweeper, local.parse_worktrees(listed)


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


def last_merged(found: Sequence[Finished]) -> Finished | None:
    """The finished worktree whose work merged last.

    Args:
        found: the finished worktrees.

    Returns:
        It, or None when none merged.
    """
    merged = [each for each in found if each.merged]
    return max(merged, key=lambda each: each.merged, default=None)


MERGED_WORK = (local.Reason.MERGED, local.Reason.IN_BASE)


def judge(
    look: dead.Look,
    now: datetime.datetime,
    each: Finished,
    pressure: Pressure | None = None,
) -> Judged:
    """Apply the safety test to one finished worktree.

    Under disk pressure a merged worktree's own ``.pitboss-live`` marker is not
    honored, except on the one whose work merged last: a marker outlives its
    work (keyword: auto-clean, ``rules.md``, "Checkouts and disk").

    Args:
        look: what to look at and keep.
        now: the time now.
        each: the finished worktree.
        pressure: what the pressure does to markers, or None when the disk has room.

    Returns:
        What the test said.
    """
    last = pressure is not None and each == pressure.last
    forgiven = pressure is not None and each.reason in MERGED_WORK and not last
    path = each.worktree.path
    unmarked = frozenset({path.resolve()}) if forgiven else look.unmarked
    eyes = dataclasses.replace(look, unmarked=unmarked)
    cutoff = now.timestamp() - look.settings.idle_hours * 3600
    held, kept, found = dead.verdict(eyes, path, cutoff)
    ignored = forgiven and found.marked
    refused = untracked.files_but_marker if ignored else untracked.files
    why = held or kept or refused(look.run, path)
    return Judged(found=each, size=found.size, why=why, ignored=ignored, last=last)


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
    note = (
        "; its .pitboss-live marker is ignored: a worktree merged after it"
        if each.ignored
        else ""
    )
    said = (
        f"{Marker.REMOVED_WORKTREE.text} {path} ({each.found.reason.value}{note}){verb}"
    )
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
    if made.why:
        return Outcome(said=kept_line(made), freed=0, kept=True, removed=False)
    said, removed = removal_line(action, look, made)
    return Outcome(said=said, freed=made.size * removed, kept=False, removed=removed)


def remove_lines(
    look: dead.Look,
    action: Action,
    moment: datetime.datetime,
    decide: Decide = local.finished_reason,
) -> Sequence[str]:
    """Remove the finished worktrees that pass the safety test, saying what happened.

    Each is judged right before its removal, and the worktree lists are pruned
    last.

    Args:
        look: what to look at and keep.
        action: how to remove them.
        moment: the time now.
        decide: whether a worktree is finished.

    Returns:
        A line for each worktree, then the totals.
    """
    found = find(look, decide)
    weighed = dataclasses.replace(action, pressure=action.weigh(found))
    steps = [act(look, weighed, moment, each) for each in found]
    git(action.run, look.settings.project.main_clone, "worktree", "prune")
    freed = disk.size_text(sum(each.freed for each in steps))
    verb = "would be freed" if action.dry else "freed"
    removed = sum(each.removed for each in steps)
    kept = sum(each.kept for each in steps)
    total = f"worktrees: {removed} removed, {freed} {verb}; {kept} kept"
    return [*(each.said for each in steps), total]

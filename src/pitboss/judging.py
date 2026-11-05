"""A finished worktree and what is said of it: its marker, under pressure and by age.

A merged worktree's own ``.pitboss-live`` marker is not honored under disk
pressure, except on the one whose work merged last. Whatever the disk, it is
not honored either once it is older than a worker's task (``workhours``, 6
hours). Keyword: auto-clean, ``worktrees.judge``.
"""

import dataclasses
from typing import Sequence

from . import local, workhours


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
        stale: whether the marker was not honored because it is older than a
            worker's task.
        last: whether it is the merged worktree that merged last, under pressure.
    """

    found: Finished
    size: int
    why: str
    ignored: bool = False
    stale: bool = False
    last: bool = False


def last_merged(found: Sequence[Finished]) -> Finished | None:
    """The finished worktree whose work merged last.

    Args:
        found: the finished worktrees.

    Returns:
        It, or None when none merged.
    """
    merged = [each for each in found if each.merged]
    return max(merged, key=lambda each: each.merged, default=None)


def marker_note(each: Judged) -> str:
    """What a removal says of a marker that was not honored.

    Args:
        each: the judgement.

    Returns:
        The words that follow the reason, or empty when the marker was honored
        or there was none.
    """
    if each.stale:
        return (
            f"; its .pitboss-live marker is older than {workhours.TASK_HOURS} hours,"
            " longer than a worker runs"
        )
    if each.ignored:
        return "; its .pitboss-live marker is ignored: a worktree merged after it"
    return ""

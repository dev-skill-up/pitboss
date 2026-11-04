"""When a finished worktree's work merged (keyword: auto-clean).

Under disk pressure the worktree whose work merged last keeps its
``.pitboss-live`` marker and the older merged ones lose theirs
(``worktrees.under_pressure``).
"""

import datetime

from . import local
from .running import git


def seconds(stamp: str) -> float:
    """Read an ISO 8601 time.

    Args:
        stamp: the time.

    Returns:
        Its seconds since the epoch, or 0 when it is not a time.
    """
    try:
        return datetime.datetime.fromisoformat(stamp).timestamp()
    except ValueError:
        return 0.0


def pull_merged_at(sweeper: local.Sweeper, worktree: local.Worktree) -> float:
    """When the PR of a worktree merged.

    Args:
        sweeper: what the decision needs.
        worktree: the worktree.

    Returns:
        The merge time of its PR.
    """
    return seconds(sweeper.outcomes[worktree.branch].merged_at)


def tip_committed_at(sweeper: local.Sweeper, worktree: local.Worktree) -> float:
    """When the tip of a worktree that has no PR was committed.

    Args:
        sweeper: what the decision needs.
        worktree: the worktree.

    Returns:
        The commit time of its tip.
    """
    main_clone = sweeper.settings.project.main_clone
    shown = git(sweeper.run, main_clone, "log", "-1", "--format=%ct", worktree.head)
    return float(shown.strip())


def never_merged(sweeper: local.Sweeper, worktree: local.Worktree) -> float:
    """The merge time of a worktree whose work did not merge.

    Args:
        sweeper: what the decision needs.
        worktree: the worktree.

    Returns:
        0.
    """
    return 0.0


MERGE_TIMES = {
    local.Reason.MERGED: pull_merged_at,
    local.Reason.IN_BASE: tip_committed_at,
}


def merged_at(
    sweeper: local.Sweeper, worktree: local.Worktree, reason: local.Reason
) -> float:
    """When a finished worktree's work merged.

    Args:
        sweeper: what the decision needs.
        worktree: the worktree.
        reason: why it is finished.

    Returns:
        The PR's merge time; the tip's commit time when it has no PR and its
        tip is in the base branch; else 0.
    """
    return MERGE_TIMES.get(reason, never_merged)(sweeper, worktree)

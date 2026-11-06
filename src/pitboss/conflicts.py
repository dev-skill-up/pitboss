"""A PR that conflicts with its base (keyword: conflict)."""

from typing import Protocol

from . import shapes, steps


class HasPull(Protocol):
    """What the conflict rules read of a PR."""

    @property
    def pull(self) -> shapes.Pull:
        """Return the PR."""


def is_dirty(pull: shapes.Pull) -> bool:
    """Whether a PR's merge state is a conflict with its base.

    Args:
        pull: the PR.

    Returns:
        True on a merge conflict.
    """
    return pull.mergeable_state is shapes.MergeState.DIRTY


def has_conflict(pr: HasPull) -> bool:
    """Whether the PR conflicts with its base.

    Args:
        pr: the PR.

    Returns:
        True on a merge conflict.
    """
    return is_dirty(pr.pull)


def merge_unless_conflict(pr: HasPull) -> steps.Next:
    """Merge, or resolve the conflict of the head first.

    Args:
        pr: the PR.

    Returns:
        The merge step, or the worker's conflict resolution.
    """
    return conflict_step(pr) or steps.merge()


def conflict_step(pr: HasPull) -> steps.Next | None:
    """The worker's resolution of a conflict, when the PR has one.

    Args:
        pr: the PR.

    Returns:
        The step, or None when the PR does not conflict with its base.
    """
    return steps.worker(steps.Task.RESOLVE_CONFLICT) if has_conflict(pr) else None

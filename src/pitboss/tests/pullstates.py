"""A PR's state with nothing read but the PR, for ``replace``.

``PullState`` is in the World's closure, so it has no field default (plan 6.1,
P3; keyword: one-path).
"""

import dataclasses
from typing import AbstractSet

from .. import draftfacts, flowstate, handbacks, shapes


def bare(pull: shapes.Pull) -> flowstate.PullState:
    """The state of a PR with no label, check, review or comment.

    Args:
        pull: the PR.

    Returns:
        The state, trusting members, with no draft question.
    """
    return flowstate.PullState(
        pull=pull,
        labels=frozenset(),
        checks=(),
        graded=(),
        comments=(),
        trusted=frozenset({"MEMBER"}),
        undraft_clear=False,
        relock=False,
        draft=draftfacts.NONE,
        recorded=flowstate.Recorded(
            unchanged=frozenset(), handed=handbacks.NOT_REQUIRED
        ),
    )


def with_recorded(
    pr: flowstate.PullState,
    *,
    unchanged: AbstractSet[str] | None = None,
    handed: handbacks.HandedBack | None = None,
) -> flowstate.PullState:
    """A PR with some of what the caller read of the base and the worktree.

    Args:
        pr: the PR.
        unchanged: the reviewed heads since which no code moved; kept when None.
        handed: what the worktree recorded; kept when None.

    Returns:
        The PR with that recorded.
    """
    was = pr.recorded
    recorded = flowstate.Recorded(
        unchanged=was.unchanged if unchanged is None else unchanged,
        handed=was.handed if handed is None else handed,
    )
    return dataclasses.replace(pr, recorded=recorded)

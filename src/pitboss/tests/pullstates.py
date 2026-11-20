"""A PR's state with nothing read but the PR, for ``replace``.

``PullState`` is in the World's closure, so it has no field default (plan 6.1,
P3; keyword: one-path).
"""

from .. import draftfacts, flowstate, shapes


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
        unchanged=frozenset(),
    )

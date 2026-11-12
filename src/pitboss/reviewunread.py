"""A review of an approved Plan with no Execution grade (keyword: review-unread).

Bats PR 650 (2026-11-11 18:45Z): the reviewer's comment had ``Plan: approved
(fixed)`` and a verdict but no ``Execution:`` line, so the flow read it as a
review of the Plan alone and went on printing ``review it``. The sweep names such
a comment so that the reviewer is sent back to write the line (pitboss#444, case
28).
"""

from typing import Sequence

from . import flowstate, gradeline, shapes

PREFIX = "REVIEW UNREAD"


def without_execution(state: flowstate.PullState) -> Sequence[str]:
    """The reviews of the head that follow an approved Plan and grade no Execution.

    Args:
        state: what is recorded of the PR.

    Returns:
        The address of each regular review of the current head that has a
        ``Plan:`` grade and no ``Execution:`` grade although an earlier regular
        review approved the Plan, oldest first.
    """
    graded = sorted(flowstate.regular_reviews(state), key=lambda each: each.when)
    found: list[str] = []
    for index, each in enumerate(graded):
        if _lacks_execution(state, each, graded[:index]):
            found.extend(_address(state, each))
    return found


def _lacks_execution(
    state: flowstate.PullState, review: shapes.Graded, earlier: Sequence[shapes.Graded]
) -> bool:
    # a Plan grade at the head, no Execution grade, after an approved Plan
    approving = shapes.Verdict.APPROVED in {before.plan for before in earlier}
    at_head = state.pull.head.sha.startswith(review.sha)
    plan_alone = review.plan is not None and review.execution is None
    return approving and at_head and (plan_alone or _no_grades(state, review))


def _no_grades(state: flowstate.PullState, review: shapes.Graded) -> bool:
    # a prose-only or verdict-only review: its comment has neither grade line
    bodies = [each.body for each in state.comments if each.created_at == review.when]
    return bool(bodies) and not any(
        gradeline.present(bodies[0], prefix)
        for prefix in (gradeline.PLAN_PREFIX, gradeline.EXECUTION_PREFIX)
    )


def _address(state: flowstate.PullState, review: shapes.Graded) -> Sequence[str]:
    return [
        comment.url or review.when
        for comment in state.comments
        if comment.created_at == review.when
    ] or [review.when]


def line(reference: str, url: str) -> str:
    """The sweep's line for one such review.

    Args:
        reference: the PR.
        url: the review's address.

    Returns:
        The line.
    """
    return (
        f"{PREFIX}: {reference}: {url} has no Execution: line; the Plan is"
        " approved, so the reviewer writes `Execution: <verdict>` beside the"
        " `Verdict:` line"
    )

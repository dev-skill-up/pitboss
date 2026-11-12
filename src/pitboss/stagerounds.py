"""The rounds that decide escalation are kept per stage (keyword: stage-rounds, pitboss#222).

dev-skill-up/pitboss#217: the Plan went through two rejections and an Opus
ruling, was approved in round 3, and the first Execution rejection then went to
the owner, because the ruling counted as the Execution's too. A ruling written
before the Plan was approved is the Plan stage's; it leaves the Execution its own
rounds: a fix, then a ruling on a second rejection, and the owner after that
ruling. A ruling written after the approval is the Execution's, and
``flow.rejected`` reads it as before.
"""

from . import flowstate, shapes, steps

Verdict = shapes.Verdict


def plan_stage_ruled(pr: flowstate.PullState) -> bool:
    """Whether the newest ruling is the Plan stage's.

    Args:
        pr: the PR.

    Returns:
        True when a ruling is recorded after a rejection of the Plan and before any
        approval of it.
    """
    ruling = flowstate.newest_ruling(pr)
    if ruling is None:
        return False
    reviews = flowstate.regular_reviews(pr)
    rejected = any(
        each.plan is Verdict.CHANGES_NEEDED and each.when < ruling.created_at
        for each in reviews
    )
    approved = any(
        each.plan is Verdict.APPROVED and each.when < ruling.created_at
        for each in reviews
    )
    return rejected and not approved


def execution_step(pr: flowstate.PullState, review: shapes.Graded) -> steps.Next | None:
    """The step after an Execution rejection when only the Plan stage had a ruling.

    Args:
        pr: the PR.
        review: the newest review that counts, which rejects the Execution.

    Returns:
        The fix of the review for the first Execution rejection after that
        ruling, the ruling for a later one; None when the ruling is the
        Execution's or there is none.
    """
    ruling = flowstate.newest_ruling(pr)
    if (
        ruling is None
        or not plan_stage_ruled(pr)
        or review.plan is Verdict.CHANGES_NEEDED
    ):
        return None
    rejections = [
        each
        for each in flowstate.regular_reviews(pr)
        if each.execution is Verdict.CHANGES_NEEDED
        and ruling.created_at < each.when <= review.when
    ]
    return (
        steps.opus_ruling()
        if len(rejections) > 1
        else steps.worker(steps.Task.FIX_EXECUTION)
    )

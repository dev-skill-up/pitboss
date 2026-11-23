"""The rounds that decide escalation are kept per stage.

The keyword is stage-rounds, pitboss#222.

dev-skill-up/pitboss#217: the Plan went through two rejections and an Opus
ruling, was approved in round 3, and the first Execution rejection then went to
the owner, because the ruling counted as the Execution's too. A ruling written
before the Plan was approved is the Plan stage's; it leaves the Execution its
own rounds: a fix, then a ruling on a second rejection, and the owner after that
ruling. A ruling written after the approval is the Execution's, and
``flow.rejected`` reads it as before.
"""

from typing import Sequence

from . import handbacks, shapes, steps

Verdict = shapes.Verdict


def plan_stage_ruled(
    ruling: shapes.Comment | None, reviews: Sequence[shapes.Graded]
) -> bool:
    """Whether the newest ruling is the Plan stage's.

    Args:
        ruling: the PR's newest ruling (``flowstate.newest_ruling``).
        reviews: its regular reviews (``flowquestions.regular_reviews``).

    Returns:
        True when a ruling is recorded after a rejection of the Plan and before any
        approval of it.
    """
    if ruling is None:
        return False
    rejected = any(
        each.plan is Verdict.CHANGES_NEEDED and each.when < ruling.created_at
        for each in reviews
    )
    approved = any(
        each.plan is Verdict.APPROVED and each.when < ruling.created_at
        for each in reviews
    )
    return rejected and not approved


def execution_step(
    ruling: shapes.Comment | None,
    reviews: Sequence[shapes.Graded],
    newest: shapes.Graded,
    handed: handbacks.HandedBack,
) -> steps.Next | None:
    """The step after an Execution rejection when only the Plan stage had a ruling.

    Args:
        ruling: the PR's newest ruling.
        reviews: its regular reviews.
        newest: the newest review that counts, which rejects the Execution.
        handed: what the PR's worktree recorded of the hand-backs: a rejection of a
            head and body no worker handed back is no round (keyword: standing).

    Returns:
        The fix of the review for the first Execution rejection after that
        ruling, the ruling for a later one; None when the ruling is the
        Execution's or there is none.
    """
    if (
        ruling is None
        or not plan_stage_ruled(ruling, reviews)
        or newest.plan is Verdict.CHANGES_NEEDED
    ):
        return None
    later = _rejections(reviews, (ruling.created_at, newest.when), handed)
    return steps.opus_ruling() if later > 1 else steps.worker(steps.Task.FIX_EXECUTION)


def _rejections(
    reviews: Sequence[shapes.Graded],
    window: tuple[str, str],
    handed: handbacks.HandedBack,
) -> int:
    # the distinct handed-back states the Execution was rejected at, after the
    # ruling, up to the newest review
    rejected = {
        (each.sha, each.body)
        for each in reviews
        if each.execution is Verdict.CHANGES_NEEDED
        and window[0] < each.when <= window[1]
        and handbacks.covers_state(handed, each.sha, each.body)
    }
    return len(rejected)

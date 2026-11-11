"""The review flow of a PR: the one step it is at (keyword: review-flow).

``next_step`` is the owner's pseudo code of 2026-10-30 (pitboss#107), branch
for branch in the same order. The only changes are the syntax and what the
lint requires: a function that long is cut at the pseudo code's own section
comments, each section ending in a call to the next. Every question it asks is
a function of its own below, answered from what is recorded of the PR (its
body, labels, comments, reviews and checks), so a wrong step is a bug in one
of them and never in the flow. The pseudo code's second function is
``rulings.after_opus_ruling``, whose table (``flowstate.AFTER``) the flow reads
when a ruling is not yet followed by a review. ``rules.md``, "Plan first",
points here.
"""

from typing import Sequence

from . import (
    bodydigest,
    conflicts,
    draftfacts,
    flowstate,
    plancheckflow,
    planbody,
    reviewfindings,
    rulingwords,
    shapes,
    steps,
)

Verdict = shapes.Verdict
Graded = shapes.Graded
Ci = flowstate.Ci
PullState = flowstate.PullState
is_ruling = flowstate.is_ruling
read_ruling = flowstate.read_ruling
newest_ruling = flowstate.newest_ruling
readable_ruling = flowstate.readable_ruling
has_conflict = conflicts.has_conflict
AFTER = flowstate.AFTER
AS_RULED = flowstate.AS_RULED


def is_paused_for_owner(pr: PullState) -> bool:
    """Whether the PR carries the pause label.

    Args:
        pr: the PR.

    Returns:
        True when it is paused for the owner.
    """
    return steps.PAUSED_LABEL in pr.labels


def _of_head(pr: PullState, reviews: Sequence[Graded]) -> Sequence[Graded]:
    return [each for each in reviews if pr.pull.head.sha.startswith(each.sha)]


def newest_counting_review(pr: PullState) -> Graded | None:
    """The newest regular review of the current head.

    A GitHub review is no regular review (the pseudo code reads regular
    reviews only, as every other question here does). A revision of the plan
    ends with an empty commit, so the review of a plan that was revised names
    an older head and does not count; ``plan_approved`` carries its approval.
    The newest review of the head that records a body digest other than the
    PR body's now does not count either (keyword: body-digest, pitboss#147):
    a body fix is answered by a re-review or, while CI quotes are missing, by theirs.

    Args:
        pr: the PR.

    Returns:
        The review, or None when no regular review names the current head or
        the newest one read another body.
    """
    found = _of_head(pr, flowstate.regular_reviews(pr))
    newest = max(found, key=lambda each: each.when, default=None)
    if newest and bodydigest.changed(newest.body, bodydigest.digest(pr.pull.body)):
        return None
    return newest


def is_draft(pr: PullState) -> bool:
    """Whether the PR is a draft.

    Args:
        pr: the PR.

    Returns:
        True for a draft.
    """
    return pr.pull.draft


def can_undraft(pr: PullState) -> bool:
    """Whether the runner pressure, the quiet period and the holds allow it.

    Args:
        pr: the PR.

    Returns:
        True when marking the PR ready may be done now.
    """
    return pr.undraft_clear


def plan_approved(pr: PullState) -> bool:
    """Whether some regular review graded the plan approved.

    Args:
        pr: the PR.

    Returns:
        True once one did; it is never graded again.
    """
    return any(each.plan is Verdict.APPROVED for each in flowstate.regular_reviews(pr))


def get_plan_rejections(pr: PullState) -> int:
    """How many regular reviews graded the plan changes needed.

    A red CI is no review and is never counted.

    Args:
        pr: the PR.

    Returns:
        The count.
    """
    reviews = flowstate.regular_reviews(pr)
    return sum(each.plan is Verdict.CHANGES_NEEDED for each in reviews)


def ci_result(pr: PullState) -> Ci | None:
    """The result of the checks on the current head.

    Args:
        pr: the PR.

    Returns:
        RED when a check failed, GREEN when all finished and none failed,
        None while some run or none has started.
    """
    if any(each.failed for each in pr.checks):
        return Ci.RED
    if not pr.checks or any(not each.finished for each in pr.checks):
        return None
    return Ci.GREEN


def plan_rejected_again(pr: PullState) -> bool:
    """Whether the plan was rejected more than once.

    Args:
        pr: the PR.

    Returns:
        True from the second rejection on.
    """
    return get_plan_rejections(pr) >= 2


def rejected(pr: PullState, review: Graded, first: steps.Next) -> steps.Next:
    """The step after a rejection: the ruling's, the owner's or the first one.

    Args:
        pr: the PR.
        review: the newest review that counts, which rejects.
        first: the step when no ruling is recorded.

    Returns:
        With a readable ruling: the owner when the review was posted after the
        ruling, else the ruling's own step (no review has followed it yet, and
        the table's later steps stay unwired: a worker's push moves the head
        and the ordinary review gate takes over); with none: ``first``.
    """
    answered = flowstate.readable_comment(pr)
    if answered is None:
        return first
    posted, ruled = answered
    if review.when > posted.created_at:  # the ruling was used, still rejected
        return steps.pause_for_owner()
    return ruled_step(pr, ruled)


def ruled_step(pr: PullState, ruled: rulingwords.Ruling) -> steps.Next:
    """The step a readable ruling gives, before any review follows it.

    Args:
        pr: the PR.
        ruled: what the ruling rules.

    Returns:
        The merge (or the conflict's resolution) for ``execution is
        approved``, else the first step of the ruling's row of ``AFTER``.
    """
    if ruled is rulingwords.Ruling.EXECUTION_IS_APPROVED:
        return conflicts.merge_unless_conflict(pr)  # CI is green, the gate above passed
    return AFTER[ruled][0]


def unfixed_execution(pr: PullState) -> steps.Next | None:
    """The step of an Execution rejection that no code has answered.

    Args:
        pr: the PR, whose Plan is approved.

    Returns:
        With such a rejection (``flowstate.unfixed_rejection``): the step of
        ``rejected``, the fix of the Execution when the ruling revised the Plan.
    """
    rejecting = flowstate.unfixed_rejection(pr)
    if rejecting is None:
        return None
    answered = flowstate.readable_comment(pr)
    if answered and flowstate.plan_edit_ruled(pr, rejecting.when):
        return steps.worker(steps.Task.FIX_EXECUTION, answered[0].url)
    return rejected(pr, rejecting, steps.opus_ruling())


def plan_unrun(pr: PullState, review: Graded | None) -> steps.Next | None:
    """The round of a Plan approved alone after a ruling (keyword: plan-alone).

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        ``plancheckflow.plan_unrun`` for the PR's readable ruling.
    """
    return plancheckflow.plan_unrun(pr, review, flowstate.readable_comment)


def rejection_step(pr: PullState, review: Graded) -> steps.Next | None:
    """The step after a review that rejects the Plan or the Execution.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        With the Plan rejected: the step of ``rejected`` for the Plan (a first
        rejection is the worker's, the fix round when the findings name a file
        of the tree, else the Plan revision; a second: Opus rules). With the
        Execution rejected: that of the Execution, whose first step is the
        ruling. None when the review rejects neither.
    """
    first = steps.opus_ruling()
    if review.plan is Verdict.CHANGES_NEEDED:
        named = reviewfindings.named_by(pr.comments, pr.trusted, review.when)
        task = steps.Task.FIX_ROUND if named else steps.Task.REVISE_PLAN
        first = first if plan_rejected_again(pr) else steps.worker(task)
    elif review.execution is not Verdict.CHANGES_NEEDED:
        return None
    return rejected(pr, review, first)


def next_step(pr: PullState) -> steps.Next:
    """The one step a PR is at (the owner's pseudo code, 2026-10-30).

    Args:
        pr: the PR.

    Returns:
        The step.
    """
    if is_paused_for_owner(pr):
        return steps.wait_for_owner()

    # the newest Opus ruling must be readable, and an approved Plan stays as it is
    if held := flowstate.ruling_hold(pr):  # keyword: plan-digest (pitboss#172)
        return held

    # keyword: conflict-first (pitboss#148, Opus ruling on #181): a conflict is a
    # fix at every stage but while steps.WAITS holds it (PLAN_EDITED included)
    review = newest_counting_review(pr)
    if has_conflict(pr):
        return waiting_step(pr, review) or steps.worker(steps.Task.RESOLVE_CONFLICT)

    # ---- before any review: the first work on a PR; a relock PR fixes no ticket
    # and has no body to write: its review (pitboss#126), or ``pinsonly`` (#34)
    if not (pr.relock or planbody.has_plan_execution_body(pr.pull.body)):
        return steps.worker(steps.Task.FIRST_ROUND)

    return draft_gate(pr, review)


def waiting_step(pr: PullState, review: Graded | None) -> steps.Next | None:
    """The wait that a rejection is at (keyword: wait-first, pitboss#183).

    A fix (of a conflict or of a red CI) is not offered while the rejection step
    is a ruling due, a pause or a ruling that escalates.

    Args:
        pr: the PR.
        review: the newest review that counts, or None.

    Returns:
        The wait step, or None when there is no review or its step is no wait.
    """
    held = rejection_step(pr, review) if review else None
    return held if held is not None and held.step in steps.WAITS else None


def draft_gate(pr: PullState, review: Graded | None) -> steps.Next:
    """The draft gate of ``next_step`` (a red check but the Plan's is fixed first).

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    if is_draft(pr):
        ready = steps.undraft() if can_undraft(pr) else steps.wait_for_undraft()
        if pr.draft.no_drafts:  # keyword: no-drafts (pitboss#390): never reviewed
            return ready
        # keyword: draft-review (pitboss#156, #176): a rejection is fixed first
        rejection = rejection_step(pr, review) if review else None
        red = draftfacts.failed_besides(pr.checks, pr.draft.plan_review_check)
        if red and not rejection:  # keyword: draft-red-ci
            return ci_gate(pr, review)
        if rejection or not plan_approved(pr):
            alone = plancheckflow.review(pr, steps.Stage.PLAN_ONLY)
            return rejection or flowstate.draft_plan_review(pr, alone)
        unrun = plan_unrun(pr, review)  # keyword: plan-alone
        # keyword: run-e2e (pitboss#199); else the CI gate on the undrafted head
        return unrun or flowstate.e2e_step(pr) or ready

    return ci_gate(pr, review)


def ci_gate(pr: PullState, review: Graded | None) -> steps.Next:
    """The CI gate of ``next_step``: nothing below runs until CI is green.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    ci = ci_result(pr)  # GREEN, RED, or None (still running or not started)
    if ci is None:
        return steps.wait_for_ci()  # nobody works or reviews meanwhile
    if ci is Ci.RED:  # a red CI is never a rejection, and it fixes no wait
        return waiting_step(pr, review) or steps.worker(steps.Task.FIX_CI)

    if review is None:
        if ruled := flowstate.ruling_unapplied(pr):
            return ruled_step(pr, ruled)
        if plan_approved(pr):  # approved while it was a draft
            return unfixed_execution(pr) or plancheckflow.execution_review(
                pr, steps.Stage.EXECUTION_ONLY
            )
        alone = flowstate.plan_rejected_last(pr)
        both = steps.Stage.PLAN_AND_EXECUTION
        return plancheckflow.review(pr, steps.Stage.PLAN_ONLY if alone else both)

    return plan_gate(pr, review)


def plan_gate(pr: PullState, review: Graded) -> steps.Next:
    """The Plan part of ``next_step``: the Plan is not approved.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    return rejection_step(pr, review) or execution_gate(pr, review)


def execution_gate(pr: PullState, review: Graded) -> steps.Next:
    """The Execution part of ``next_step``: the Plan is approved, never regraded.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    if review.execution is None:  # plan approved by a plan-only review
        # keyword: plan-alone, the same round as a draft's: no condition on the draft
        return (
            plan_unrun(pr, review)
            or unfixed_execution(pr)
            or plancheckflow.execution_review(pr, steps.Stage.EXECUTION_AGAINST_PLAN)
        )

    # approved: ``rejection_step`` took the Execution that needs changes
    return conflicts.merge_unless_conflict(pr)  # CI is green, the gate above passed

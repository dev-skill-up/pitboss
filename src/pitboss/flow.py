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

from typing import Callable, Sequence

from . import (
    bodydigest,
    conflicts,
    flowstate,
    plancheckflow,
    planbody,
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


def _regular_reviews(pr: PullState) -> Sequence[Graded]:
    regular = [each for each in pr.graded if each.comment]
    return sorted(regular, key=lambda each: each.when)


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
    found = _of_head(pr, _regular_reviews(pr))
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
    return any(each.plan is Verdict.APPROVED for each in _regular_reviews(pr))


def get_plan_rejections(pr: PullState) -> int:
    """How many regular reviews graded the plan changes needed.

    A red CI is no review and is never counted.

    Args:
        pr: the PR.

    Returns:
        The count.
    """
    rejected = [
        each for each in _regular_reviews(pr) if each.plan is Verdict.CHANGES_NEEDED
    ]
    return len(rejected)


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


def rejected(
    pr: PullState,
    review: Graded,
    task: steps.Task,
    again: Callable[[PullState], bool],
) -> steps.Next:
    """The step after a rejection: the ruling's, the owner, the worker or Opus.

    Args:
        pr: the PR.
        review: the newest review that counts, which rejects.
        task: what the worker does on the first rejection.
        again: says whether the rejected part was already given its round.

    Returns:
        With a readable ruling: the owner when the review was posted after the
        ruling, else the ruling's own step (no review has followed it yet, and
        the table's later steps stay unwired: a worker's push moves the head
        and the ordinary review gate takes over); with none: the worker's
        round, else Opus.
    """
    answered = flowstate.readable_comment(pr)
    if answered is None:
        return steps.opus_ruling() if again(pr) else steps.worker(task)
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


def ruling_first(pr: PullState) -> bool:
    """Whether a rejected Execution is given an Opus ruling before any fix round.

    Args:
        pr: the PR.

    Returns:
        True, always: the Execution stage starts with a ruling (keyword:
        ruling-first, pitboss#390; the Plan stage starts with a fix round).
    """
    return True


def rejection_step(pr: PullState, review: Graded) -> steps.Next | None:
    """The step after a review that rejects the Plan or the Execution.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        With the Plan rejected: the step of ``rejected`` for the Plan (the
        ruling used and still rejected pauses; a first rejection is the
        worker's, the fix round when the findings name a file of the tree and
        the Plan revision otherwise; a second is not converging: Opus rules).
        With the Execution rejected: that of the Execution, whose first step is
        the ruling. None when the review rejects neither.
    """
    if review.plan is Verdict.CHANGES_NEEDED:
        task = steps.Task.FIX_ROUND if review.names_change else steps.Task.REVISE_PLAN
        return rejected(pr, review, task, plan_rejected_again)
    if review.execution is Verdict.CHANGES_NEEDED:
        return rejected(pr, review, steps.Task.FIX_EXECUTION, ruling_first)
    return None


def unfixed_execution(pr: PullState) -> steps.Next | None:
    """The step of an Execution rejection that no code has answered.

    A Plan revised and approved after an Execution rejection leaves a head that
    only an empty commit moved, and its review grades the Plan alone: the
    rejected Execution still stands (keyword: unfixed-execution, pitboss#390).

    Args:
        pr: the PR, whose Plan is approved.

    Returns:
        With the newest Execution verdict changes needed and no code moved since
        its head: the ruling when none is recorded, the pause when a ruling
        before the next round was used, else the ruling's step (the fix
        round); None otherwise.
    """
    graded = [each for each in _regular_reviews(pr) if each.execution is not None]
    rejecting = graded[-1] if graded else None
    if rejecting is None or rejecting.execution is not Verdict.CHANGES_NEEDED:
        return None
    if not pr.unchanged_since(rejecting.sha):
        return None
    answered = flowstate.readable_comment(pr)
    if answered is None:
        return steps.opus_ruling()
    posted, ruled = answered
    if rejecting.when > posted.created_at:
        return steps.pause_for_owner()
    if ruled is rulingwords.Ruling.REVISE_THE_PLAN:
        return steps.fix_execution(posted.url)  # the Plan is revised
    return ruled_step(pr, ruled)


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
    """The draft gate of ``next_step`` (CI is not waited for, but for the Plan review).

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    if is_draft(pr):
        if pr.no_drafts:  # keyword: no-drafts (pitboss#390): marked ready, not reviewed
            return steps.undraft() if can_undraft(pr) else steps.wait_for_undraft()
        # keyword: draft-review (pitboss#156, #176): a rejection is fixed first
        rejection = rejection_step(pr, review) if review else None
        if rejection or not plan_approved(pr):
            alone = plancheckflow.review(pr, steps.Stage.PLAN_ONLY)
            return rejection or flowstate.draft_plan_review(pr, alone)
        if unrun := flowstate.plan_unrun(pr, review):  # keyword: plan-alone
            return unrun
        if e2e := flowstate.e2e_step(pr):  # keyword: run-e2e (pitboss#199)
            return e2e
        if can_undraft(pr):  # pressure passes, the CI-action spacing and holds allow
            return steps.undraft()  # the next step is the CI gate on the undrafted head
        # plan approved but cannot be undrafted yet: wait for the window
        return steps.wait_for_undraft()

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
        # keyword: no-drafts (pitboss#390): one review covers the Plan and the Execution
        alone = flowstate.plan_rejected_last(pr) and not pr.no_drafts
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
        if unrun := flowstate.plan_unrun(pr, review):  # keyword: plan-alone
            return unrun  # the same round as a draft's: no condition on the draft
        return unfixed_execution(pr) or plancheckflow.execution_review(
            pr, steps.Stage.EXECUTION_AGAINST_PLAN
        )

    # approved: ``rejection_step`` took the Execution that needs changes
    return conflicts.merge_unless_conflict(pr)  # CI is green, the gate above passed

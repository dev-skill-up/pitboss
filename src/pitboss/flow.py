"""The review flow of a PR: the one step it is at (keyword: review-flow).

``next_step`` is the owner's pseudo code of 2026-10-30 (pitboss#107), branch for
branch, cut where the lint needs it; every question is a function below, answered
from what is recorded of the PR. Its second function is ``rulings.after_opus_ruling``.
"""

from typing import Sequence

from . import workerselect
from . import (
    checkoutcome,
    conflicts,
    e2estep,
    expansion,
    evidence,
    floworder,
    flowquestions,
    flowstate,
    impossiblecard,
    headline,
    plancheckflow,
    planbody,
    reviewfindings,
    ruleconflicts,
    rulingafter,
    rulingwords,
    shapes,
    stagerounds,
    standing,
    steps,
    usedstep,
)

current_for = expansion.current_for
Subject = expansion.Subject
Verdict = shapes.Verdict
Graded = shapes.Graded
Ci = flowquestions.Ci
PullState = flowstate.PullState
is_ruling = flowstate.is_ruling
read_ruling = flowstate.read_ruling
newest_ruling = flowstate.newest_ruling
readable_ruling = flowstate.readable_ruling
has_conflict = conflicts.has_conflict
AFTER = rulingafter.AFTER
Row = floworder.Row[PullState, steps.Move]
newest_counting_review = flowquestions.newest_counting_review
plan_approved = flowquestions.plan_approved
plan_revised = flowquestions.plan_revised
get_plan_rejections = flowquestions.get_plan_rejections


TERMINAL = steps.IMPOSSIBLE  # keyword: impossible-state: the queue moves past the PR


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
    staged = stagerounds.execution_step(  # keyword: stage-rounds
        flowstate.newest_ruling(pr),
        flowquestions.regular_reviews(pr),
        review,
        pr.handed,
    )
    posted, ruled = answered
    again = flowquestions.used_again(pr, review, posted)
    after = usedstep.of(review, posted) if again else ruled_step(pr, ruled)
    return after if staged is None else staged


def ruled_step(pr: PullState, ruled: rulingwords.Ruling) -> steps.Next:
    """The step a readable ruling gives, before any review follows it.

    Args:
        pr: the PR.
        ruled: what the ruling rules.

    Returns:
        The merge (or its conflict) for ``execution is approved``, else the step
        of the row of ``AFTER`` (keyword: body-only-round).
    """
    if ruled is rulingwords.Ruling.EXECUTION_IS_APPROVED:
        return conflicts.merge_unless_conflict(pr)  # CI is green, the gate above passed
    if ruled is rulingwords.Ruling.REVISE_THE_PLAN and plan_revised(pr):
        # the ruling is applied: the revised Plan is graded again (current-for)
        return _plan_review(pr)
    if ruled is not rulingwords.Ruling.DO_THESE_STEPS:
        return AFTER[ruled][0]
    # handed back since, or pushed for a PR no worker holds
    if flowstate.ruling_applied(pr):
        return standing.reviewed(pr, steps.Stage.RULING_STEPS)
    return workerselect.worker(steps.Task.RULING_STEPS, flowstate.ruling_address(pr))


def unfixed_execution(pr: PullState) -> steps.Next | None:
    """The step of an Execution rejection that no code has answered.

    Args:
        pr: the PR, whose Plan is approved.

    Returns:
        With such a rejection (``flowquestions.unfixed_rejection``): the step of
        ``rejected``, the fix of the Execution when the ruling revised the Plan.
    """
    rejecting = flowquestions.unfixed_rejection(pr)
    if rejecting is None:
        return None
    answered = flowstate.readable_comment(pr)
    if answered and flowstate.plan_edit_ruled(pr, rejecting.when):
        return workerselect.worker(steps.Task.FIX_EXECUTION, answered[0].url)
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
        first = first if get_plan_rejections(pr) >= 2 else workerselect.worker(task)
    elif review.execution is not Verdict.CHANGES_NEEDED:
        return None
    return rejected(pr, review, first)


def next_step(pr: PullState) -> steps.Move:
    """The one step a PR is at (the owner's pseudo code, 2026-10-30).

    The first row of ``ROWS`` that holds decides (keyword: flow-order, item 11).

    Args:
        pr: the PR.

    Returns:
        The step.
    """
    step = next(row.step(pr) for row in ROWS if row.holds(pr))
    acted = isinstance(step, steps.Next) and step.step in steps.HELD
    held = acted and pr.draft.hold  # keyword: hold-scope, B20
    return steps.Idle.RUNNER_PRESSURE if held else step


def waiting_step(pr: PullState, review: Graded | None) -> steps.Next | None:
    """The owed ruling or pause a rejection is at (keyword: wait-first, pitboss#183).

    A fix (of a conflict or of a red CI) is not offered while the rejection step
    is a ruling due, a pause or a ruling that escalates.

    Args:
        pr: the PR.
        review: the newest review that counts, or None.

    Returns:
        That step, or None when there is no review or its step is no such step.
    """
    held = rejection_step(pr, review) if review else None
    return held if held is not None and held.step in steps.UNRESOLVED else None


def draft_gate(pr: PullState, review: Graded | None) -> steps.Move:
    """The draft gate of ``next_step`` (a red check but the Plan's is fixed first).

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    if pr.pull.draft:
        ready = _ready(pr)
        if pr.draft.no_drafts:  # keyword: no-drafts (pitboss#390): never reviewed
            # a red CI is fixed by the worker before the undraft (draft-red-ci)
            return ci_gate(pr, review) if _red(pr) else ready
        # keyword: draft-review (pitboss#156, #176): a rejection is fixed first
        rejection = rejection_step(pr, review) if review else None
        if _red(pr) and not rejection:  # keyword: draft-red-ci
            return ci_gate(pr, review)
        if rejection or not plan_approved(pr):
            alone = _plan_review(pr)
            return rejection or flowstate.draft_plan_review(pr, alone)
        unrun = plan_unrun(pr, review)  # keyword: plan-alone
        # keyword: run-e2e (pitboss#199); else the CI gate on the undrafted head
        return unrun or e2estep.e2e_step(pr) or ready

    return ci_gate(pr, review)


def _red(pr: PullState) -> bool:
    # keyword: draft-red-ci: a failed check is fixed, the Plan review's too (quire#1134)
    return checkoutcome.result(pr.checks) is checkoutcome.Ci.RED


def _ready(pr: PullState) -> steps.Move:
    # an approved draft is undrafted when the window allows, else no actor takes it
    return steps.undraft() if pr.undraft_clear else steps.Idle.UNDRAFT_WINDOW


def ci_gate(pr: PullState, review: Graded | None) -> steps.Move:
    """The CI gate of ``next_step``: nothing below runs until CI is green.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    ci = checkoutcome.result(pr.checks)  # GREEN, RED, or None (running or none)
    if ci is None:
        return steps.Idle.CI_RUN  # nobody works or reviews meanwhile
    if ci is Ci.RED:  # a red CI is never a rejection, and it fixes no wait
        return waiting_step(pr, review) or workerselect.worker(steps.Task.FIX_CI)

    return unreviewed_step(pr) if review is None else plan_gate(pr, review)


def unreviewed_step(pr: PullState) -> steps.Next:
    """The step of a green PR with no review that counts.

    Args:
        pr: the PR.

    Returns:
        The step.
    """
    if ruled := flowstate.ruling_unapplied(pr):
        return ruled_step(pr, ruled)
    if plan_approved(pr):  # approved while it was a draft
        return unfixed_execution(pr) or plancheckflow.execution_review(
            pr, standing.reviewed(pr, steps.Stage.EXECUTION_ONLY)
        )
    alone = flowquestions.plan_rejected_last(pr) or plan_revised(pr)
    both = steps.Stage.PLAN_AND_EXECUTION
    stage = steps.Stage.PLAN_ONLY if alone else both
    return plancheckflow.review(pr, standing.reviewed(pr, stage))


def _plan_review(pr: PullState) -> steps.Next:
    # ``plancheckflow.review`` of the Plan alone
    return plancheckflow.review(pr, standing.reviewed(pr, steps.Stage.PLAN_ONLY))


def _execution_due(pr: PullState) -> steps.Next:
    # the review of the Execution against the approved Plan, at its standing
    return standing.reviewed(pr, steps.Stage.EXECUTION_AGAINST_PLAN)


def plan_gate(pr: PullState, review: Graded) -> steps.Next:
    """The Plan part of ``next_step``: the Plan is not approved.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    return (
        rejection_step(pr, review)
        or (_plan_review(pr) if plan_revised(pr) else None)
        or execution_gate(pr, review)
    )


def execution_gate(pr: PullState, review: Graded) -> steps.Next:
    """The Execution part of ``next_step``: the Plan is approved, never regraded.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    do_steps = rulingwords.Ruling.DO_THESE_STEPS
    if flowstate.ruling_unapplied(pr) is do_steps:  # keyword: ruling-first (A2)
        return ruled_step(pr, do_steps)
    if review.execution is None:  # plan approved by a plan-only review
        # keyword: plan-alone, the same round as a draft's: no condition on the draft
        return (
            plan_unrun(pr, review)
            or unfixed_execution(pr)
            or plancheckflow.execution_review(pr, _execution_due(pr))
        )

    # approved; a ruling to do its steps after the approval voided it above (#467)
    return conflicts.merge_unless_conflict(pr)


def _ruling_held(pr: PullState) -> steps.Move:
    # the newest Opus ruling must be readable, and an approved Plan stays as it is
    # (keyword: plan-digest, pitboss#172)
    held = flowstate.ruling_hold(pr)
    if held is None:  # pragma: no cover
        return steps.Idle.RUNNER_PRESSURE  # unreachable: the row holds only when held
    return rulingafter.held_step(held, flowstate.ruling_unapplied(pr))


def _conflict_step(pr: PullState) -> steps.Next:
    # keyword: conflict-first (pitboss#148, #181): a fix but while UNRESOLVED holds
    wait = waiting_step(pr, newest_counting_review(pr))
    return wait or workerselect.worker(steps.Task.RESOLVE_CONFLICT)


def _stale_body(pr: PullState) -> bool:
    # keyword: stale-head
    head = pr.pull.head.sha
    stale = evidence.stale_heads(pr.pull.body, head)
    return headline.is_stale(pr.pull.body, head) or bool(stale)


def _refreshed(pr: PullState, found: steps.Move) -> steps.Move:
    # a body with an older head's line is no hand-back of this head: refresh it
    owed = isinstance(found, steps.Next) and (
        found.step in steps.REFRESHED or found.task is steps.Task.HAND_BACK
    )
    stale = owed and _stale_body(pr)
    return workerselect.worker(steps.Task.REFRESH_BODY) if stale else found


def _no_body(pr: PullState) -> bool:
    # before any review: the first work on a PR; a relock PR fixes no ticket and
    # has no body to write: its review (pitboss#126), or ``pinsonly`` (#34)
    return not (pr.relock or planbody.has_plan_execution_body(pr.pull.body))


# The one table of the order in which ``next_step`` decides: the first row that
# holds wins. ``STATED`` gives the reason for the order of each two rows that can
# hold at once, and a test fails for a pair that has none (keyword: flow-order).
ROWS: Sequence[Row] = (
    Row(
        name="impossible",
        holds=lambda pr: impossiblecard.ended(pr.comments, pr.trusted),
        step=lambda pr: TERMINAL,
    ),
    Row(
        name="ruling-hold",
        holds=lambda pr: bool(flowstate.ruling_hold(pr)),
        step=_ruling_held,
    ),
    Row(name="rule-conflict", holds=ruleconflicts.holds, step=ruleconflicts.ruling),
    Row(name="conflict", holds=has_conflict, step=_conflict_step),
    Row(
        name="first-round",
        holds=_no_body,
        step=lambda pr: workerselect.worker(steps.Task.FIRST_ROUND),
    ),
    Row(
        name="gates",
        holds=lambda pr: True,
        step=lambda pr: _refreshed(pr, draft_gate(pr, newest_counting_review(pr))),
    ),
)
STATED = floworder.STATED

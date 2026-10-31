"""The review flow of a PR: the one step it is at (keyword: review-flow).

``next_step`` is the owner's pseudo code of 2026-10-30 (pitboss#107), branch
for branch in the same order. The only changes are the syntax and what the
lint requires: a function that long is cut at the pseudo code's own section
comments, each section ending in a call to the next. Every question it asks is
a function of its own below, answered from what is recorded of the PR (its
body, labels, comments, reviews and checks), so a wrong step is a bug in one
of them and never in the flow. The pseudo code's second function is
``rulings.after_opus_ruling``. ``rules.md``, "Plan first", points here.
"""

import dataclasses
import enum
import re
from typing import AbstractSet, Callable, Sequence

from . import sessionurl, shapes, steps

_PLAN_HEADING = re.compile(r"^## Plan\s*$", re.MULTILINE)
_EXECUTION_HEADING = re.compile(r"^## Execution\s*$", re.MULTILINE)
Verdict = shapes.Verdict
Graded = shapes.Graded


class Ci(enum.Enum):
    """The result of the checks on the current head, once finished.

    Attributes:
        GREEN: every check finished and none failed.
        RED: a check failed.
    """

    GREEN = enum.auto()
    RED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullState:
    """What is recorded of one PR; every question reads only this.

    Attributes:
        pull: the PR.
        labels: its labels.
        checks: the check runs of its current head.
        graded: every review that counts, in no particular order.
        comments: its issue comments.
        trusted: the author associations whose comments count.
        undraft_clear: whether the runner pressure and the quiet period allow
            an undraft now (read by the caller; the flow does not look).
        merges_only_since: says whether the current head differs from a
            reviewed head by merge commits only (the caller reads the base).
    """

    pull: shapes.Pull
    labels: AbstractSet[str]
    checks: Sequence[shapes.CheckRun]
    graded: Sequence[Graded]
    comments: Sequence[shapes.Comment]
    trusted: AbstractSet[str]
    undraft_clear: bool = False
    merges_only_since: Callable[[str], bool] = lambda sha: False


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

    Args:
        pr: the PR.

    Returns:
        The review, or None when no regular review names the current head.
    """
    found = _of_head(pr, _regular_reviews(pr))
    return max(found, key=lambda each: each.when, default=None)


def has_plan_execution_body(pr: PullState) -> bool:
    """Whether the PR's body has a Plan section and an Execution section.

    Args:
        pr: the PR.

    Returns:
        True when both headings (``## Plan``, ``## Execution``) are there.
    """
    body = pr.pull.body
    return bool(_PLAN_HEADING.search(body) and _EXECUTION_HEADING.search(body))


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


def is_ruling(body: str) -> bool:
    """Whether a comment is a recorded Opus ruling.

    Args:
        body: the comment.

    Returns:
        True when its first line is exactly ``Opus ruling``.
    """
    lines = sessionurl.lines(body)
    return bool(lines) and lines[0].rstrip() == steps.RULING_FIRST_LINE


def opus_used(pr: PullState) -> bool:
    """Whether a trusted comment records an Opus ruling.

    Args:
        pr: the PR.

    Returns:
        True when one does.
    """
    return any(
        is_ruling(each.body) and each.author_association in pr.trusted
        for each in pr.comments
    )


def execution_fixed_since_plan_approval(pr: PullState) -> bool:
    """Whether a worker pushed an execution fix after the plan was approved.

    Read from the reviews: the execution was graded changes needed on the
    approved plan at a head that more than merge commits separate from the
    current one (a merge of the base is no fix: ``merges_only_since``).

    Args:
        pr: the PR.

    Returns:
        True when an earlier execution rejection names such a head.
    """
    approved = False
    for each in _regular_reviews(pr):
        approved = approved or each.plan is Verdict.APPROVED
        rejecting = approved and each.execution is Verdict.CHANGES_NEEDED
        if rejecting and not (_of_head(pr, [each]) or pr.merges_only_since(each.sha)):
            return True
    return False


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


def is_dirty(pull: shapes.Pull) -> bool:
    """Whether a PR's merge state is a conflict with its base.

    Args:
        pull: the PR.

    Returns:
        True on a merge conflict.
    """
    return pull.mergeable_state is shapes.MergeState.DIRTY


def has_conflict(pr: PullState) -> bool:
    """Whether the PR conflicts with its base.

    Args:
        pr: the PR.

    Returns:
        True on a merge conflict.
    """
    return is_dirty(pr.pull)


def plan_rejected_again(pr: PullState) -> bool:
    """Whether the plan was rejected more than once.

    Args:
        pr: the PR.

    Returns:
        True from the second rejection on.
    """
    return get_plan_rejections(pr) >= 2


def rejected(
    pr: PullState, task: steps.Task, again: Callable[[PullState], bool]
) -> steps.Next:
    """The step after a rejection: pause, the worker's round, or Opus.

    Args:
        pr: the PR.
        task: what the worker does on the first rejection.
        again: says whether the rejected part was already given its round.

    Returns:
        The owner after a ruling, else the worker, else Opus.
    """
    if opus_used(pr):  # the ruling was used, still rejected
        return steps.pause_for_owner()
    if not again(pr):  # first rejection
        return steps.worker(task)
    return steps.opus_ruling()  # not converging


def next_step(pr: PullState) -> steps.Next:
    """The one step a PR is at (the owner's pseudo code, 2026-10-30).

    Args:
        pr: the PR.

    Returns:
        The step.
    """
    if is_paused_for_owner(pr):
        return steps.wait_for_owner()

    review = newest_counting_review(pr)

    # ---- before any review: the first work on a PR
    if not has_plan_execution_body(pr):  # first time on this PR
        return steps.worker(steps.Task.FIRST_ROUND)

    return draft_gate(pr, review)


def draft_gate(pr: PullState, review: Graded | None) -> steps.Next:
    """The draft gate of ``next_step`` (a draft runs no CI), then the CI gate.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    if is_draft(pr):
        if can_undraft(pr):  # pressure passes, the CI-action spacing and holds allow
            return steps.undraft()  # the next step is the CI gate on the undrafted head
        if not plan_approved(pr):
            return steps.regular_review(
                steps.Stage.PLAN_ONLY
            )  # a rejection is a Plan one
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
    if ci is Ci.RED:
        return steps.worker(steps.Task.FIX_CI)  # a red CI is never a rejection

    if review is None:
        if plan_approved(pr):  # approved while it was a draft
            return steps.regular_review(steps.Stage.EXECUTION_ONLY)
        return steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)

    return plan_gate(pr, review)


def plan_gate(pr: PullState, review: Graded) -> steps.Next:
    """The Plan part of ``next_step``: the Plan is not approved.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    if review.plan is Verdict.CHANGES_NEEDED:  # a Plan rejection
        # the ruling used and still rejected pauses; a first rejection is the
        # worker's; a second (>= 2) is not converging: Opus rules
        return rejected(pr, steps.Task.REVISE_PLAN, plan_rejected_again)

    return execution_gate(pr, review)


def execution_gate(pr: PullState, review: Graded) -> steps.Next:
    """The Execution part of ``next_step``: the Plan is approved, never regraded.

    Args:
        pr: the PR.
        review: the newest review that counts.

    Returns:
        The step.
    """
    if review.execution is None:  # plan approved by a plan-only review
        return steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN)

    if review.execution is Verdict.APPROVED:
        if not has_conflict(pr):
            return steps.merge()  # CI is green, the gate above passed
        return steps.worker(steps.Task.RESOLVE_CONFLICT)

    # review.execution is changes needed: execution rejected on an approved plan
    # a rejection after the ruling pauses; the first execution grade is the
    # worker's; once the fix was pushed, this execution is rejected: Opus rules
    return rejected(pr, steps.Task.FIX_EXECUTION, execution_fixed_since_plan_approval)

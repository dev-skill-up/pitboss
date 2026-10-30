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
from typing import AbstractSet, Sequence

from . import shapes, steps

_PLAN_HEADING = re.compile(r"^## Plan\s*$", re.MULTILINE)
_EXECUTION_HEADING = re.compile(r"^## Execution\s*$", re.MULTILINE)
Verdict = shapes.Verdict


class Ci(enum.Enum):
    """The result of the checks on the current head, once finished.

    Attributes:
        GREEN: every check finished and none failed.
        RED: a check failed.
    """

    GREEN = enum.auto()
    RED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Graded:
    """A review as the flow reads it.

    Attributes:
        sha: the head it reviewed (possibly abbreviated).
        when: when it was written (ISO 8601).
        plan: what its ``Plan:`` line grades, None with no such line.
        execution: its verdict, None for a review of the plan alone.
        comment: whether it is a regular review (a comment in the form, not a
            GitHub review).
    """

    sha: str
    when: str
    plan: Verdict | None
    execution: Verdict | None
    comment: bool = True


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
    """

    pull: shapes.Pull
    labels: AbstractSet[str]
    checks: Sequence[shapes.CheckRun]
    graded: Sequence[Graded]
    comments: Sequence[shapes.Comment]
    trusted: AbstractSet[str]
    undraft_clear: bool = False


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


def _names(review: Graded, head: str) -> bool:
    return head.startswith(review.sha)


def newest_counting_review(pr: PullState) -> Graded | None:
    """The newest review of the current head.

    A revision of the plan ends with an empty commit, so the review of a
    plan that was revised names an older head and does not count; the plan's
    approval is carried by ``plan_approved``.

    Args:
        pr: the PR.

    Returns:
        The review, or None when no review names the current head.
    """
    found = [each for each in pr.graded if _names(each, pr.pull.head.sha)]
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
    lines = body.splitlines()
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
    approved plan at a head other than the current one, so the head moved
    since (a merge of the base moves it too).

    Args:
        pr: the PR.

    Returns:
        True when an earlier execution rejection names another head.
    """
    approved = False
    rejected: list[Graded] = []
    for each in _regular_reviews(pr):
        approved = approved or each.plan is Verdict.APPROVED
        if approved and each.execution is Verdict.CHANGES_NEEDED:
            rejected.append(each)
    return any(not _names(each, pr.pull.head.sha) for each in rejected)


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
    if not pr.checks or not all(each.finished for each in pr.checks):
        return None
    return Ci.GREEN


def has_conflict(pr: PullState) -> bool:
    """Whether the PR conflicts with its base.

    Args:
        pr: the PR.

    Returns:
        True on a merge conflict.
    """
    return pr.pull.mergeable_state is shapes.MergeState.DIRTY


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
        if opus_used(pr):  # the ruling was used, still rejected
            return steps.pause_for_owner()
        if get_plan_rejections(pr) == 1:  # first rejection
            return steps.worker(steps.Task.REVISE_PLAN)
        return steps.opus_ruling()  # second rejection (>= 2): not converging

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
    if opus_used(pr):  # a reviewer rejected the fix after the ruling
        return steps.pause_for_owner()
    if not execution_fixed_since_plan_approval(pr):  # first execution grade
        return steps.worker(steps.Task.FIX_EXECUTION)
    return steps.opus_ruling()  # this execution is rejected

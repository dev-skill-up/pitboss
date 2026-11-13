"""The questions the review flow asks of a PR's reviews and checks (review-flow).

``flow`` decides the step from their answers; each is answered from what is
recorded of the PR.
"""

import enum
from typing import AbstractSet, Protocol, Sequence

from . import bodydigest, draftfacts, expansion, plandigest, shapes

current_for = expansion.current_for
Subject = expansion.Subject
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


class PullState(Protocol):
    """What the questions read of a PR (``flowstate.PullState`` has it)."""

    @property
    def pull(self) -> shapes.Pull:
        """Return the PR."""

    @property
    def checks(self) -> Sequence[shapes.CheckRun]:
        """Return the check runs of its current head."""

    @property
    def graded(self) -> Sequence[shapes.Graded]:
        """Return every review that counts, in no particular order."""

    @property
    def draft(self) -> draftfacts.Draft:
        """Return what the caller read for a draft."""

    @property
    def unchanged(self) -> AbstractSet[str]:
        """Return the reviewed heads since which no code moved."""


def _of_head(pr: PullState, reviews: Sequence[Graded]) -> Sequence[Graded]:
    head = Subject.HEAD
    return [each for each in reviews if current_for(head, each.sha, pr.pull.head.sha)]


def newest_counting_review(pr: PullState) -> Graded | None:
    """The newest regular review of the current head.

    A GitHub review is no regular review. A revision of the plan pushes nothing, so the
    review of a plan that was revised records an older body digest and does not
    count; ``plan_approved`` carries its approval. The newest
    review of the head that records a body digest other than the PR body's
    does not count either (keyword: body-digest, pitboss#147).

    Args:
        pr: the PR.

    Returns:
        The review, or None when no regular review names the current head or
        the newest one read another body.
    """
    found = _of_head(pr, regular_reviews(pr))
    newest = max(found, key=lambda each: each.when, default=None)
    now = bodydigest.digest(pr.pull.body)
    if newest and not current_for(Subject.BODY, newest.body, now):
        return None
    return newest


def plan_approved(pr: PullState) -> bool:
    """Whether some regular review approved the Plan as it is now.

    Args:
        pr: the PR.

    Returns:
        True when one did and is current for the Plan section's digest
        (keyword: current-for); a Plan revised since is graded again.
    """
    section = plandigest.section(pr.pull.body)
    return any(
        each.plan is Verdict.APPROVED
        and current_for(Subject.PLAN, each.plan_digest, section)
        for each in regular_reviews(pr)
    )


def plan_revised(pr: PullState) -> bool:
    """Whether a review approved a Plan that has been revised since.

    Args:
        pr: the PR.

    Returns:
        True when a regular review approved the Plan and none approved it as it
        is now: its re-review is due (keyword: current-for).
    """
    approving = any(each.plan is Verdict.APPROVED for each in regular_reviews(pr))
    return approving and not plan_approved(pr)


def get_plan_rejections(pr: PullState) -> int:
    """How many regular reviews graded the plan changes needed.

    A red CI is no review and is never counted.

    Args:
        pr: the PR.

    Returns:
        The count.
    """
    reviews = regular_reviews(pr)
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


def plan_rejected_last(pr: PullState) -> bool:
    """Whether the newest regular review graded the Plan changes needed.

    With no review of the current head, this is a Plan written after its
    rejection, and it is graded alone, as a draft's is (keyword:
    plan-review-listed, pitboss#167).

    Args:
        pr: the PR.

    Returns:
        True when the newest regular review of any head rejected the Plan and
        the repository has drafts (keyword: no-drafts, pitboss#390).
    """
    regular = regular_reviews(pr)
    rejected = bool(regular) and regular[-1].plan is Verdict.CHANGES_NEEDED
    return rejected and not pr.draft.no_drafts


def unfixed_rejection(pr: PullState) -> shapes.Graded | None:
    """The newest Execution verdict if it rejects, unanswered (unfixed-execution).

    Args:
        pr: the PR.

    Returns:
        The Execution-graded review if it rejects and no code moved, else None.
    """
    asked = asked_rejection(pr)
    return asked if asked is not None and asked.sha in pr.unchanged else None


def asked_rejection(pr: PullState) -> shapes.Graded | None:
    """The rejecting review whose head the read asks about (unfixed-execution).

    Args:
        pr: the PR.

    Returns:
        The newest Execution verdict if it rejects and the head moved since it
        (other than by a body fix), else None.
    """
    graded = [each for each in regular_reviews(pr) if each.execution is not None]
    rejecting = graded[-1] if graded else None
    if rejecting is None or rejecting.execution is not Verdict.CHANGES_NEEDED:
        return None
    moved = not expansion.current_for(  # else a body fix
        expansion.Subject.HEAD, rejecting.sha, pr.pull.head.sha
    )
    return rejecting if moved else None


def regular_reviews(pr: PullState) -> Sequence[shapes.Graded]:
    """The regular reviews of a PR, oldest first (no GitHub review).

    Args:
        pr: the PR.

    Returns:
        The reviews.
    """
    regular = [each for each in pr.graded if each.comment]
    return sorted(regular, key=lambda each: each.when)

"""The changes-needed limit of a PR's review rounds (keyword: round-limit).

The skill's rules ("Plan first, and two rounds of changes needed") call for an
Opus ruling when the plan is not approved after two reviews, or when a review
asks for changes after the plan was approved, and for a pause when a review
asks for changes again after the ruling. This module reads those rounds from
the PR's comments: the ``Plan:`` line and the verdict of each review, and a
comment whose first line is ``Opus ruling``.
"""

import dataclasses
import enum
from typing import AbstractSet, Callable, Iterable

from . import config, gradeline, shapes

RULING_FIRST_LINE = "Opus ruling"
VerdictOf = Callable[[str], shapes.Verdict | None]


class Limit(enum.Enum):
    """Where a PR's review rounds stand against the limit.

    Attributes:
        NONE: the limit is not reached, or the newest review does not ask for
            changes, or the ruling was recorded and no review came after it.
        RULING_DUE: the limit is reached, the newest review asks for changes
            and no ruling is recorded.
        PAUSE: the newest review asks for changes after a recorded ruling.
    """

    NONE = enum.auto()
    RULING_DUE = enum.auto()
    PAUSE = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Rounds:
    """What the comments read so far say.

    Attributes:
        rejections: plan grades of changes needed before any grade approved.
        plan_approved: whether a review graded the plan approved.
        reached: whether the limit was reached at some review.
        ruled: whether a ruling is recorded.
        asks: whether the newest review asks for changes.
        after_ruling: whether the newest review came after a recorded ruling.
    """

    rejections: int = 0
    plan_approved: bool = False
    reached: bool = False
    ruled: bool = False
    asks: bool = False
    after_ruling: bool = False


def is_ruling(body: str) -> bool:
    """Whether a comment is a recorded ruling.

    Args:
        body: the comment.

    Returns:
        True when its first line is exactly ``Opus ruling``.
    """
    lines = body.splitlines()
    return bool(lines) and lines[0].rstrip() == RULING_FIRST_LINE


def plan_grade(body: str, form: config.ReviewForm) -> shapes.Verdict | None:
    """The grade of the ``Plan:`` line of a review.

    Args:
        body: the review comment.
        form: the form reviews take (its two verdict words).

    Returns:
        The grade of the first ``Plan:`` line, or None when no line grades it
        (the review says nothing of the plan).
    """
    found = gradeline.line_approved(
        body, gradeline.PLAN_PREFIX, form.approved, form.changes_needed
    )
    if found is None:
        return None
    return shapes.Verdict.APPROVED if found else shapes.Verdict.CHANGES_NEEDED


def after_ruling(state: Rounds) -> Rounds:
    """The state once a ruling is read.

    Args:
        state: the state before.

    Returns:
        The state with the ruling recorded.
    """
    return dataclasses.replace(state, ruled=True)


def after_review(
    state: Rounds, grade: shapes.Verdict | None, verdict: shapes.Verdict
) -> Rounds:
    """The state once a review is read.

    Args:
        state: the state before.
        grade: what its ``Plan:`` line says, if it has one.
        verdict: its verdict.

    Returns:
        The state with the review counted.
    """
    asks = verdict is shapes.Verdict.CHANGES_NEEDED
    approved = state.plan_approved or grade is shapes.Verdict.APPROVED
    rejected = grade is shapes.Verdict.CHANGES_NEEDED and not approved
    rejections = state.rejections + int(rejected)
    return dataclasses.replace(
        state,
        rejections=rejections,
        plan_approved=approved,
        reached=state.reached or rejections >= 2 or (asks and approved),
        asks=asks,
        after_ruling=state.ruled,
    )


def limit_of(state: Rounds) -> Limit:
    """Where the rounds read stand.

    Args:
        state: the state after the newest comment.

    Returns:
        PAUSE when the newest review asks for changes after a ruling,
        RULING_DUE when it asks and the limit is reached with no ruling, else
        NONE.
    """
    if not state.asks:
        return Limit.NONE
    if state.after_ruling:
        return Limit.PAUSE
    return Limit.NONE if state.ruled or not state.reached else Limit.RULING_DUE


def step(
    state: Rounds, body: str, form: config.ReviewForm, verdict_of: VerdictOf
) -> Rounds:
    """The state once one trusted comment is read.

    Args:
        state: the state before.
        body: the comment.
        form: the form reviews take.
        verdict_of: reads a comment as a review (see ``read``).

    Returns:
        The state after a ruling or a review, else the state unchanged.
    """
    if is_ruling(body):
        return after_ruling(state)
    verdict = verdict_of(body)
    if verdict is None:
        return state
    return after_review(state, plan_grade(body, form), verdict)


def read(
    posted: Iterable[shapes.Comment],
    trusted: AbstractSet[str],
    form: config.ReviewForm,
    verdict_of: VerdictOf,
) -> Limit:
    """Read a PR's comments against the limit.

    Only comments by trusted authors count, in the order written. A review
    counts when ``verdict_of`` reads it. The limit is reached at the
    second plan rejection, or at a review that asks for changes once a review
    graded the plan approved (that review included). It is judged by the
    newest review.

    Args:
        posted: the PR's issue comments.
        trusted: the author associations whose comments count.
        form: the form reviews take.
        verdict_of: reads a comment as a review of the repository: None when
            it is none, else its verdict.

    Returns:
        The limit.
    """
    state = Rounds()
    for item in sorted(posted, key=lambda each: each.created_at):
        if item.author_association in trusted:
            state = step(state, item.body, form, verdict_of)
    return limit_of(state)

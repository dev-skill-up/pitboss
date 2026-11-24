"""A ruling's steps done in the body alone (pitboss#462, pitboss#507).

GitHub gives no time for a body edit, so the record of the round is the worker's
hand-back that saw the ruling: a clean ``Plan check`` is no such record (keyword:
body-only-round, standing).
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import flow, handbacks, plancheckflow, shapes, steps
from . import blank, test_flow
from .. import witnessstates
from .derivedhand import held
from .checkcomment import clean_text
from .test_flow import expect, state
from . import reviewsteps

OK = "Plan check: ok"
RULING = "https://example.org/ruling/3"
REVIEW = reviewsteps.review(steps.Stage.RULING_STEPS)
FIX = steps.worker(steps.Task.RULING_STEPS, RULING)
NOTHING = held()
HANDED = held(test_flow.HEAD)
REJECTIONS = (test_flow.FIRST_REJECTION, test_flow.SECOND_REJECTION)


def check_after(text: str, digest: str = "") -> shapes.Comment:
    """A ``Plan check`` of the Plan, written after the ruling.

    Args:
        text: the last line of the check.
        digest: the Plan digest line it records, that of the body's Plan when "".

    Returns:
        The comment.
    """
    clean = clean_text(test_flow.BODY).replace(OK, text)
    body = clean.replace(clean.splitlines()[1], digest or clean.splitlines()[1])
    return dataclasses.replace(
        blank.COMMENT,
        body=body,
        author_association="MEMBER",
        created_at="2026-10-30T00:00:04Z",
        url="https://example.org/check/4",
    )


def ruled(
    *after: shapes.Comment,
    held: handbacks.HandedBack = handbacks.NOT_REQUIRED,
    checks: Sequence[shapes.CheckRun] = (test_flow.GREEN,),
) -> flow.PullState:
    """A PR ruled ``do these steps`` after two Plan rejections.

    Args:
        *after: the comments after the ruling.
        held: what the PR shows of its hand-back.
        checks: the check runs of its head.

    Returns:
        The state.
    """
    both = state(*REJECTIONS, comments=[test_flow.ruling(3), *after], checks=checks)
    return witnessstates.with_recorded(both, handed=held)


class TestBodyOnlyRound(unittest.TestCase):
    """The step of a ruling whose steps the body alone could do."""

    def test_t462_a_push_after_the_ruling_under_a_hand_back_gives_the_review(
        self,
    ) -> None:
        """The head is handed back and a check ran after the ruling: its review."""
        pushed = dataclasses.replace(test_flow.GREEN, started_at="2026-10-30T00:00:09Z")
        expect(REVIEW, ruled(held=HANDED, checks=(pushed,)))

    def test_t462_no_hand_back_gives_the_fix(self) -> None:
        """The body names no head under a clean check."""
        expect(FIX, ruled(held=NOTHING))

    def test_t462_a_clean_check_after_the_ruling_is_no_hand_back(self) -> None:
        """A Plan check never applies a ruling (quire#1125)."""
        expect(FIX, ruled(check_after(OK), held=NOTHING))

    def test_a_pr_no_worker_holds_follows_its_reviews_and_pushes(self) -> None:
        """With no worktree the ruling is applied by a later review or push."""
        expect(FIX, ruled(check_after(OK)))

    def test_unchecked_and_review_follow_the_check(self) -> None:
        """A refused Plan is unchecked, and its review is the send-back."""
        refused = ruled(check_after("Plan check: refused, rows: 1"))
        assert_that(plancheckflow.unchecked(refused), equal_to(True))
        assert_that(plancheckflow.unchecked(ruled(check_after(OK))), equal_to(False))
        again = plancheckflow.review(refused, REVIEW)
        assert_that(again.step, equal_to(steps.Step.SEND_BACK_PLAN_CHECK))


UNCARRIED = (
    "Opus ruling\nRuling: do these steps\n\n## Steps\n\n"
    "1. body replace: a sentence the body never had => its new words, in no body\n"
)


def ruled_in_other_words(*after: shapes.Graded) -> flow.PullState:
    """A ruling with a body edit that does not show literally, then reviews.

    Args:
        *after: the reviews of the head after the ruling.

    Returns:
        The state: handed back at the head, the body carrying the edit in words of
        its own.
    """
    words = dataclasses.replace(test_flow.ruling(3), body=UNCARRIED)
    both = state(*REJECTIONS, *after, comments=[words], checks=(test_flow.GREEN,))
    return witnessstates.with_recorded(
        both, handed=held(test_flow.HEAD, "2026-10-30T00:00:08Z")
    )


class TestRulingProgress(unittest.TestCase):
    """pitboss#526 (bats-lang/dom#140): a step that no edit can end is not chosen."""

    def test_a_review_of_the_handed_back_head_ends_a_ruling_the_text_cannot(
        self,
    ) -> None:
        """The words differ and a later review approved the head: the merge."""
        later = dataclasses.replace(
            test_flow.graded(*test_flow.EVERYTHING_APPROVED, 9),
            comment=True,
        )
        assert_that(
            flow.next_step(ruled_in_other_words(later)),
            equal_to(steps.merge()),
        )

    def test_no_review_after_it_leaves_the_worker_step(self) -> None:
        """With no review the text decides: the ruling's own step."""
        assert_that(
            flow.next_step(ruled_in_other_words()),
            equal_to(FIX),
        )

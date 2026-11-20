"""A ruling's steps done in the body alone (pitboss#462).

GitHub gives no time for a body edit, so the clean ``Plan check`` newer than the
ruling is the record of the round (keyword: body-only-round).
"""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import flow, flowstate, plancheckflow, shapes, steps
from . import blank, test_flow
from .checkcomment import clean_text
from .test_flow import expect, state

OK = "Plan check: ok"
REVIEW = steps.regular_review(steps.Stage.RULING_STEPS)
FIX = steps.worker(steps.Task.RULING_STEPS, "https://example.org/ruling/3")
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


def ruled(*after: shapes.Comment) -> flow.PullState:
    """A PR ruled ``do these steps`` after two Plan rejections.

    Args:
        *after: the comments after the ruling.

    Returns:
        The state.
    """
    return state(*REJECTIONS, comments=[test_flow.ruling(3), *after])


class TestBodyOnlyRound(unittest.TestCase):
    """The step of a ruling whose steps the body alone could do."""

    def test_t462_a_clean_check_after_the_ruling_gives_the_review(self) -> None:
        """The body was fixed and checked: the review of the ruling's steps."""
        expect(REVIEW, ruled(check_after(OK)))

    def test_t462_no_check_after_the_ruling_gives_the_fix(self) -> None:
        """The body was not edited after the ruling."""
        expect(FIX, ruled())

    def test_t462_a_refusal_after_the_ruling_gives_the_fix(self) -> None:
        """The newest check of the Plan refuses it."""
        expect(FIX, ruled(check_after("Plan check: refused, rows: 1")))

    def test_a_clean_check_of_another_plan_gives_the_fix(self) -> None:
        """The check names a Plan that is not the one now."""
        expect(FIX, ruled(check_after(OK, f"Plan digest: {'0' * 16}")))

    def test_a_clean_check_before_the_ruling_is_not_since(self) -> None:
        """The nearest input checked_since must still reject: a check that is older."""
        older = dataclasses.replace(check_after(OK), created_at="2026-10-30T00:00:01Z")
        for comments, want in [([older], False), ([check_after(OK)], True)]:
            with self.subTest(len(comments)):
                pr = ruled(*comments)
                found = plancheckflow.checked_since(pr, flowstate.readable_comment)
                assert_that(found, equal_to(want))

    def test_unchecked_and_review_follow_the_check(self) -> None:
        """A refused Plan is unchecked, and its review is the fix round."""
        refused = ruled(check_after("Plan check: refused, rows: 1"))
        assert_that(plancheckflow.unchecked(refused), equal_to(True))
        assert_that(plancheckflow.unchecked(ruled(check_after(OK))), equal_to(False))
        assert_that(
            plancheckflow.review(ruled(check_after(OK)), steps.Stage.PLAN_ONLY),
            equal_to(steps.regular_review(steps.Stage.PLAN_ONLY)),
        )
        again = plancheckflow.review(refused, steps.Stage.PLAN_ONLY)
        assert_that(again.step, equal_to(steps.Step.SEND_BACK_PLAN_CHECK))

    def test_plan_unrun_needs_a_review_after_the_ruling(self) -> None:
        """With no review that counts, no round is offered."""
        found = plancheckflow.plan_unrun(ruled(), None, flowstate.readable_comment)
        assert_that(found, equal_to(None))

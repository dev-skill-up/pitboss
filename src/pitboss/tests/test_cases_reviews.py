"""I28: a review of an approved Plan with no `Execution:` line is named unread.

Case 28 of pitboss#444 (keyword: review-unread): the Execution review brief asks
for the line, and the sweep names a review that lacks it.
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brieftext, flow, reviewunread, shapes
from . import model
from .model import History, Verdict

V = Verdict
URL = "https://github.example/owner/project/pull/5#c7"
TWO_PLANS = [(3, V.APPROVED, None, 0, 0), (5, V.APPROVED, None, 0, 0)]


def state_of(
    reviews: Sequence[tuple[int, V | None, V | None, int, int]],
) -> flow.PullState:
    """The state of a PR whose reviews are given.

    Args:
        reviews: the reviews as the model has them.

    Returns:
        The state the flow reads.
    """
    return model.pull_state(model.Model(history=History(reviews=reviews)))


def named_for(body: str) -> Sequence[str]:
    """The reviews named when the head's review has a body.

    Args:
        body: the text of the review of the second Plan approval.

    Returns:
        What ``reviewunread.without_execution`` names.
    """
    comment = shapes.Comment(
        body=body, author_association="MEMBER", created_at=model.stamp(5), url=URL
    )
    state = state_of(TWO_PLANS)
    state = dataclasses.replace(state, comments=[*state.comments, comment])
    return reviewunread.without_execution(state)


class TestUnread(unittest.TestCase):
    """The brief asks for the line; the sweep names a review without it."""

    def test_i28_the_execution_brief_asks_for_the_execution_line(self) -> None:
        """Written beside `Plan: approved (fixed)`, with the REVIEW UNREAD word."""
        text = brieftext.SCOPE_EXECUTION
        assert_that(
            text, contains_string("`Plan: approved (fixed)` and an `Execution:` line")
        )
        assert_that(text, contains_string("REVIEW UNREAD"))

    def test_i28_a_plan_only_review_after_an_approved_plan_is_named(self) -> None:
        """Bats 650: Plan approved earlier, then a review with no Execution line."""
        assert_that(named_for("x"), equal_to([URL]))
        line = reviewunread.line("owner/project#5", URL)
        assert_that(line, contains_string("REVIEW UNREAD: owner/project#5"))
        assert_that(line, contains_string("has no Execution: line"))

    def test_c23_a_review_with_prose_only_is_named(self) -> None:
        """No grade line at all after an approved Plan: named, not offered silently."""
        assert_that(named_for("Looks good.\nVerdict: approved"), equal_to([URL]))

    def test_i28_a_review_with_no_comment_is_named_by_its_time(self) -> None:
        """The address falls back to the review's time."""
        state = state_of(TWO_PLANS)
        assert_that(reviewunread.without_execution(state), equal_to([model.stamp(5)]))

    def test_i28_the_first_plan_review_and_a_full_review_are_not_named(self) -> None:
        """No earlier approval, or an Execution grade: nothing."""
        first = state_of([(3, V.APPROVED, None, 0, 0)])
        full = state_of(
            [(3, V.APPROVED, None, 0, 0), (5, V.APPROVED, V.APPROVED, 0, 0)]
        )
        other_head = state_of(
            [(3, V.APPROVED, None, 0, 0), (5, V.APPROVED, None, 1, 0)]
        )
        for state in (first, full, other_head):
            assert_that(reviewunread.without_execution(state), equal_to([]))

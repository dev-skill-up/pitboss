"""A ruling to do its steps that follows an approval voids it (pitboss#467).

``slots next`` printed the merge step for pitboss#463 after an approving review
and an Opus ruling ``do these steps`` (keyword: ruling-steps-voids).
"""

import unittest

from hamcrest import assert_that, contains_string, ends_with, equal_to

from .. import flow, shapes, steps
from . import fakes, test_flow, world
from .suggestions import kind_of_third, third
from .test_flow import APPROVED, state
from .test_flow_sweep import graded as comment
from .test_flow_sweep import reading as comment_reading
from .test_commands import sweep
from .test_flow_sweep import world_with

RULING_URL = "https://example.org/ruling/2"
MERGE = steps.merge()
BODY = fakes.PLAN_AND_EXECUTION


def approved_then_ruled() -> flow.PullState:
    """A PR approved at its head, then a ruling to do these steps.

    Returns:
        The state.
    """
    review = test_flow.graded(APPROVED, APPROVED, 1)
    return state(review, comments=[test_flow.ruling(2)])


def world_of(*rounds: shapes.Comment) -> world.World:
    """PR 3 with an approving review and the given comments after it.

    Args:
        *rounds: the comments after the first review, in order.

    Returns:
        The world.
    """
    first = comment_reading(comment("approved", "approved", 1), BODY)
    return world_with([first, *rounds], body=BODY)


class TestRulingVoidsApproval(unittest.TestCase):
    """The ruling after an approval."""

    def test_the_ruling_steps_are_offered_not_the_merge(self) -> None:
        """Done-when 1: the flow offers the steps of the ruling."""
        test_flow.expect(test_flow.ruling_steps(2), approved_then_ruled())

    def test_an_approval_alone_is_merged(self) -> None:
        """The nearest input: the same approval with no ruling."""
        test_flow.expect(MERGE, state(test_flow.graded(APPROVED, APPROVED, 1)))

    def test_another_ruling_after_an_approval_does_not_void_it(self) -> None:
        """Only ``do these steps`` is read here: a split keeps the merge."""
        review = test_flow.graded(APPROVED, APPROVED, 1)
        pr = state(review, comments=[test_flow.ruling(2, line="Ruling: split")])
        test_flow.expect(MERGE, pr)

    def test_the_offered_kind_is_do_the_rulings_steps(self) -> None:
        """Done-when 1 in the world of ``slots next``."""
        here = world_of(test_flow.ruling(2))
        assert_that(kind_of_third(here), equal_to("do the steps of the Opus ruling"))

    def test_the_brief_is_the_fix_round_worker_brief_with_the_ruling(self) -> None:
        """Done-when 2: the marker ends in ``fix`` and the brief names the ruling."""
        header, brief = third(world_of(test_flow.ruling(2)))
        marker = next(each for each in brief if each.startswith("PITBOSS-SLOT:"))
        assert_that(marker, ends_with(" fix"))
        assert_that("\n".join(brief), contains_string(RULING_URL))
        assert_that(header, contains_string("project#3"))

    def test_a_review_after_the_ruling_restores_the_approval(self) -> None:
        """Done-when 3: the review follows the ruling, and the merge is offered."""
        later = comment_reading(comment("approved", "approved", 3), BODY)
        pr = state(
            test_flow.graded(APPROVED, APPROVED, 1),
            test_flow.graded(APPROVED, APPROVED, 3),
            comments=[test_flow.ruling(2)],
        )
        test_flow.expect(MERGE, pr)
        merge = "READY TO MERGE owner/project#3"
        assert_that(
            sweep(world_of(test_flow.ruling(2), later)).out, contains_string(merge)
        )

    def test_the_sweep_does_not_say_ready_to_merge_after_the_ruling(self) -> None:
        """The merge line is gone while the ruling is unapplied."""
        out = sweep(world_of(test_flow.ruling(2))).out
        assert_that("READY TO MERGE owner/project#3" in out, equal_to(False))

"""A ruling to do its steps that follows an approval voids it (pitboss#467).

``slots next`` printed the merge step for pitboss#463 after an approving review
and an Opus ruling ``do these steps`` (keyword: ruling-steps-voids).
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import flow, shapes, steps
from . import actreviewed, fakes, quietworld, test_flow, world
from .suggestions import kind_of_third, next_output
from .test_flow import APPROVED, state
from .test_flow_sweep import graded as comment
from .test_flow_sweep import reading as comment_reading
from .test_commands import sweep
from .test_flow_sweep import world_with

RULING_URL = "https://example.org/ruling/2"
MERGE = steps.merge()
# it fixes ticket 9 already, so the act review approval reads the same body
BODY = f"Fixes #9\n\n{fakes.PLAN_AND_EXECUTION}"
MERGING = actreviewed.MERGING.format(number=3)


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


def approved_sweep(here: world.World) -> str:
    """The sweep of a world whose PR 3 has an ``act review`` approval.

    Args:
        here: the world.

    Returns:
        What it printed.
    """
    actreviewed.approve(here, 3)
    return sweep(here).out


class TestRulingVoidsApproval(unittest.TestCase):
    """The ruling after an approval."""

    def test_t467_the_ruling_steps_are_offered_not_the_merge(self) -> None:
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

    def test_t467_the_offered_kind_is_do_the_rulings_steps(self) -> None:
        """Done-when 1 in the world of ``slots next``."""
        here = world_of(test_flow.ruling(2))
        assert_that(kind_of_third(here), equal_to("do the steps of the Opus ruling"))

    def test_t467_the_brief_is_the_fix_round_worker_brief_with_the_ruling(self) -> None:
        """Done-when 2: the marker ends in ``fix`` and the brief names the ruling."""
        out = next_output(world_of(test_flow.ruling(2)))
        assert_that(out, contains_string("PITBOSS-SLOT: owner/project#3 fix\n"))
        assert_that(out, contains_string(f"the comment at {RULING_URL}"))

    def test_t467_a_review_after_the_ruling_restores_the_approval(self) -> None:
        """Done-when 3: the review follows the ruling, and the merge is offered."""
        later = comment_reading(comment("approved", "approved", 3), BODY)
        pr = state(
            test_flow.graded(APPROVED, APPROVED, 1),
            test_flow.graded(APPROVED, APPROVED, 3),
            comments=[test_flow.ruling(2)],
        )
        test_flow.expect(MERGE, pr)
        swept = approved_sweep(quietworld.calm(world_of(test_flow.ruling(2), later)))
        assert_that(swept, contains_string(MERGING))

    def test_the_sweep_does_not_offer_the_merge_after_the_ruling(self) -> None:
        """The merge is no decision while the ruling is unapplied."""
        swept = approved_sweep(world_of(test_flow.ruling(2)))
        assert_that(MERGING in swept, equal_to(False))

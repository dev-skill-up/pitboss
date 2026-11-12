"""I16, I17, I26 and I34 of pitboss#444: the orders of work that the sweep prints.

I17 and I26 and I34 hold on main 482a642 too (their rules are B10 and B22 and the
fixing-PR rule of ``itempick``); the tests are named for the cases so that the
register names them. I16 is new: a relock review says it runs outside the slot.
"""

import unittest

from hamcrest import assert_that, contains_string

from . import test_flow_sweep
from .test_item_fast import NINTH, briefed, timeline_of
from .test_register_rules import shown
from .test_relock import relocked


class TestOrders(unittest.TestCase):
    """The cases of the order of work."""

    def test_i16_a_relock_review_is_run_with_pins_review_outside_the_slot(self) -> None:
        """The line of the relock PR names the command, and the PR ranks last."""
        listed = "".join(test_flow_sweep.listed_for_third(relocked()))
        assert_that(
            listed, contains_string("run outside the slot: pitboss pins-review")
        )
        assert_that(listed, contains_string("owner/project#3"))

    def test_i17_a_comment_mention_of_a_ticket_does_not_take_it(self) -> None:
        """An open PR that does not fix ticket 9 and mentions it stays no taker."""
        here = timeline_of("Fixes #1\n\nthe ruling comment mentions #9")
        briefed(here, NINTH, "start a PR: owner/project#9")

    def test_i26_a_blocked_pr_has_no_step(self) -> None:
        """The B10 tests: a blocker in the body takes the step away."""
        ran = shown(
            "test_slots_rules",
            "test_b10_a_pr_blocked_on_another_ticket_has_no_step",
            "test_b10_a_closed_blocker_or_its_own_ticket_blocks_nothing",
        )
        assert_that(ran >= 2, "both ran")

    def test_i34_a_queued_run_with_later_completed_runs_is_stuck(self) -> None:
        """The B22 tests: the line, and none without a later completed run."""
        ran = shown(
            "test_slots_rules",
            "test_b22_a_queued_run_with_later_completed_runs_is_stuck",
            "test_b22_a_recent_run_or_one_without_later_runs_is_not_stuck",
        )
        assert_that(ran >= 2, "both ran")

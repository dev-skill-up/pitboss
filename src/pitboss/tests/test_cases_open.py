"""I26 and I34 of pitboss#444: the orders of work that the sweep prints.

I26 and I34 hold on main 482a642 too (their rules are B10 and B22); the tests
are named for the cases so that the register names them.
"""

import unittest

from hamcrest import assert_that

from .test_register_rules import shown


class TestOrders(unittest.TestCase):
    """The cases of the order of work."""

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

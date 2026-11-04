"""A clean PR at a wait keeps it: no review and no CI fix is offered (pitboss#183).

The draft gate and the CI gate of ``flow.next_step`` answer before the rejection
step, so a clean draft PR at RULING DUE or PAUSE, and a clean PR with red CI at
RULING ESCALATES, must still get the wait of the rejection and be offered for
no round: ``slots next`` prints the wait line and no NEXT line for each.
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import shapes
from . import fakes, test_conflict_waits as waits, test_flow_sweep as flows, world
from .test_commands import sweep


def red_world(rounds: Sequence[shapes.Comment]) -> world.World:
    """A clean PR 3 with red CI and the comments.

    Args:
        rounds: PR 3's comments.

    Returns:
        The world.
    """
    here = flows.world_with(rounds)
    path = fakes.page(f"{world.PROJECT}/commits/{flows.HEAD}/check-runs")
    here.bodies[path] = {"check_runs": [world.RED]}
    return here


def cases() -> Sequence[tuple[str, world.World, str]]:
    """The three fixtures of the ticket, built fresh.

    Returns:
        Each: its name, its world and the start of its wait line.
    """
    paused = [*flows.RULED, flows.graded(flows.CHANGES, None, 4)]
    ruling = flows.ruled_by("Ruling: escalate to the owner")
    escalated = [*flows.TWO_PLAN_REJECTIONS, ruling]
    return [
        (
            "a clean draft at RULING DUE",
            flows.world_with(flows.TWO_PLAN_REJECTIONS, draft=True),
            flows.RULING_LINE,
        ),
        (
            "a clean draft at PAUSE",
            flows.world_with(paused, draft=True),
            flows.PAUSE_LINE,
        ),
        (
            "red CI at RULING ESCALATES",
            red_world(escalated),
            waits.ESCALATES,
        ),
    ]


class TestCleanWaits(unittest.TestCase):
    """The gates above the rejection step do not hide a wait."""

    def test_a_clean_pr_at_a_wait_prints_the_wait_and_no_next_line(self) -> None:
        """RULING DUE, PAUSE and RULING ESCALATES, each with its own gate."""
        for name, here, line in cases():
            with self.subTest(name):
                assert_that(sweep(here).out, contains_string(line))
                assert_that(flows.listed_for_third(here), equal_to([]))

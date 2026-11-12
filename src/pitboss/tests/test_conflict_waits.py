"""A dirty PR keeps its wait: a ruling or the owner comes before the conflict.

The Opus ruling on pitboss#181: ``flow.next_step`` returns a wait (``steps.WAITS``,
the paused-owner label and an unreadable ruling) before the conflict, and a
ruling's own work step after it. The sweep keeps the line of each wait next to
``CONFLICT``, and ``slots next`` lists nothing for it.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import roundline, steps
from . import fakes, test_conflict_first as first, test_flow_sweep as flows, world
from .test_commands import sweep
from .says import says

DIRTY = flows.DIRTY
ESCALATES = "RULING ESCALATES owner/project#3"
WAITING = {
    "ruling due after two plan rejections": (
        flows.TWO_PLAN_REJECTIONS,
        flows.RULING_LINE,
    ),
    "ruling due after the execution is rejected twice": (
        flows.EXECUTION_TWICE,
        flows.RULING_LINE,
    ),
    "pause after a ruling and another rejection": (
        [*flows.RULED, flows.graded(flows.CHANGES, None, 4)],
        flows.PAUSE_LINE,
    ),
    "the ruling escalates": (
        [*flows.TWO_PLAN_REJECTIONS, flows.ruled_by("Ruling: escalate to the owner")],
        ESCALATES,
    ),
}


def assert_waits(here: world.World, line: str) -> None:
    """Assert the sweep prints the wait and CONFLICT, and nothing is listed.

    Args:
        here: the world.
        line: the start of the wait's line.
    """
    swept = sweep(here).out
    assert_that(swept, contains_string(line))
    assert_that(swept, contains_string("CONFLICT owner/project#3"))
    assert_that(flows.listed_for_third(here), equal_to([]))


class TestWaits(unittest.TestCase):
    """The waits come before the conflict."""

    def test_the_waits_are_the_lines_of_the_round_line(self) -> None:
        """Every wait step has its sweep line, and no other step has one."""
        lined = set(roundline.LINES) | {steps.Step.PLAN_EDITED}
        assert_that(lined, equal_to(set(steps.WAITS)))

    def test_a_dirty_pr_held_for_the_owner_or_with_an_unreadable_ruling(self) -> None:
        """Neither is offered for a round: the gate must not move above them."""
        worlds = {
            "paused for the owner": flows.world_with(
                [], labels=[{"name": "paused-owner"}], **DIRTY
            ),
            "an unreadable ruling": flows.world_with([flows.UNREADABLE], **DIRTY),
        }
        for name, here in worlds.items():
            with self.subTest(name):
                assert_that(flows.listed_for_third(here), equal_to([]))
                says(sweep(here).out, "CONFLICT owner/project#3")

    def test_a_dirty_pr_waiting_for_a_ruling_or_the_owner(self) -> None:
        """The wait keeps its line next to CONFLICT, and no NEXT line."""
        for name, (rounds, line) in WAITING.items():
            with self.subTest(name):
                assert_waits(flows.world_with(rounds, **DIRTY), line)

    def test_a_red_ci_does_not_hide_the_wait(self) -> None:
        """The CI gate comes after the conflict gate, which keeps the wait."""
        red = flows.world_with(flows.TWO_PLAN_REJECTIONS, **DIRTY)
        path = fakes.page(f"{first.PROJECT}/commits/{flows.HEAD}/check-runs")
        red.bodies[path] = {"check_runs": [world.RED]}
        assert_waits(red, flows.RULING_LINE)

    def test_a_waiting_pr_leaves_the_resolve_set(self) -> None:
        """One fixture: three resolvable PRs and a dirty PR at RULING DUE."""
        here = first.conflicted_world()
        first.make_dirty(here, 3, "2026-08-01T00:00:00+00:00", [])
        rounds = [flows.graded(flows.CHANGES, None, 1, sha=flows.HEAD)]
        rounds.append(flows.graded(flows.CHANGES, None, 2))
        path = fakes.page(f"{first.PROJECT}/issues/3/comments")
        here.bodies[path] = [world.comment_json(each) for each in rounds]
        every = {f"{first.SLUG}#{number}" for number in (1, 2, 3)}
        first.assert_sets(here, every, every - {f"{first.SLUG}#3"})
        assert_that(sweep(here).out, contains_string(flows.RULING_LINE))

    def test_a_dirty_pr_with_a_ruling_to_carry_out_resolves_the_conflict_first(
        self,
    ) -> None:
        """The ruling's own work comes back after the conflict push."""
        for word in ("do these steps", "revise the plan"):
            with self.subTest(word):
                ruled = flows.ruled_by(f"Ruling: {word}")
                here = flows.world_with([*flows.TWO_PLAN_REJECTIONS, ruled], **DIRTY)
                swept = sweep(here).out
                assert_that(
                    "".join(flows.listed_for_third(here)),
                    contains_string("(resolve the conflict,"),
                )
                assert_that("RULING DUE" in swept, equal_to(False))
                assert_that("PAUSE owner" in swept, equal_to(False))

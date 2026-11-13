"""A green PR that is behind the base is updated, never merged (pitboss#369)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, quietworld, world
from .test_commands import sweep
from .test_flow_sweep import (
    APPROVED,
    EXECUTION_APPROVED,
    TWO_PLAN_REJECTIONS,
    graded,
)
from .test_flow_sweep import world_with as held_world

LINE = "ORCHESTRATOR: owner/project#3: `act update-branch`"


def world_with(*args: object, **changes: object) -> world.World:
    """A world as ``test_flow_sweep`` makes it, with the runners quiet (B20).

    Args:
        *args: the rounds of the world.
        **changes: the fields to replace.

    Returns:
        The world; a hold would stop the decision before BEHIND.
    """
    return quietworld.unheld(held_world(*args, **changes))  # type: ignore[arg-type]


QUEUE = "\n[merge_queue]\nrepositories = ['project']\n"
# the branch rules the gate reads: GitHub says the base has a merge queue
RULES = f"{world.PROJECT}/rules/branches/main"


class TestBehind(unittest.TestCase):
    """The decision, for an approved green PR and for the nearest inputs."""

    def test_an_approved_green_pr_that_is_behind_is_updated_not_merged(
        self,
    ) -> None:
        """The gate's BEHIND row is the decision: update the branch, never merge."""
        rounds = [*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED]
        swept = sweep(world_with(rounds, mergeable_state="behind")).out
        assert_that(swept, contains_string(LINE))
        assert_that("act merge" in swept, equal_to(False))

    def test_a_directly_approved_behind_pr_is_updated(self) -> None:
        """Approved by a review at the merge step and behind: update the branch."""
        here = world_with([graded(APPROVED, APPROVED, 9)], mergeable_state="behind")
        assert_that(sweep(here).out, contains_string(LINE))

    def test_a_queued_repository_is_not_told_to_update(self) -> None:
        """A merge-queue repository builds each entry on the base: no update."""
        rounds = [*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED]
        here = world_with(rounds, mergeable_state="behind")
        extra = world.EXTRA.format(ledger=here.ledger) + QUEUE
        fakes.settings(here.workspace, extra)
        here.bodies[RULES] = [{"type": "merge_queue", "parameters": {}}]
        assert_that(LINE in sweep(here).out, equal_to(False))

    def test_a_clean_pr_or_one_with_no_approval_is_not_told_to_update(self) -> None:
        """Clean is not behind; behind and not approved is not at the merge step."""
        rounds = [*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED]
        clean = sweep(world_with(rounds)).out
        unapproved = sweep(
            world_with(TWO_PLAN_REJECTIONS, mergeable_state="behind")
        ).out
        assert_that([LINE in clean, LINE in unapproved], equal_to([False] * 2))

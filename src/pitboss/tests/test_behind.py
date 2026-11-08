"""A green PR that is behind the base says BEHIND, with no merge offer (pitboss#369)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, world
from .test_commands import sweep
from .test_flow_sweep import (
    APPROVED,
    EXECUTION_APPROVED,
    TWO_PLAN_REJECTIONS,
    graded,
    world_with,
)

LINE = (
    "BEHIND: update the branch, then the merge-main proof (bats merge-proof)"
    " is the review"
)
QUEUE = "\n[merge_queue]\nrepositories = ['project']\n"


def offers(swept: str) -> list[bool]:
    """Whether the sweep offers a merge: ready, by hand, or auto-merge to arm.

    Args:
        swept: the sweep's output.

    Returns:
        One flag for each of the three lines.
    """
    words = ("READY TO MERGE", "MERGE BY HAND", "AUTO MERGE OFF")
    return [word in swept for word in words]


class TestBehind(unittest.TestCase):
    """The line, for an approved green PR and for the nearest inputs."""

    def test_an_approved_green_pr_that_is_behind_gets_the_line_and_no_merge(
        self,
    ) -> None:
        """BEHIND before any merge offer; the body-head command is named."""
        rounds = [*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED]
        swept = sweep(world_with(rounds, mergeable_state="behind")).out
        assert_that(swept, contains_string(LINE))
        assert_that(swept, contains_string("pitboss body-head owner/project#3"))
        assert_that(offers(swept), equal_to([False] * 3))

    def test_a_directly_approved_behind_pr_gets_no_merge_offer(self) -> None:
        """Auto-merge off and approved by a review: BEHIND, and no merge offer."""
        here = world_with([graded(APPROVED, APPROVED, 9)], mergeable_state="behind")
        swept = sweep(here).out
        assert_that(swept, contains_string("BEHIND:"))
        assert_that(offers(swept), equal_to([False] * 3))

    def test_a_queued_repository_is_not_told_behind(self) -> None:
        """A merge-queue repository builds each entry on the base: no BEHIND."""
        rounds = [*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED]
        here = world_with(rounds, mergeable_state="behind")
        extra = world.EXTRA.format(ledger=here.ledger) + QUEUE
        fakes.settings(here.workspace, extra)
        assert_that("BEHIND:" in sweep(here).out, equal_to(False))

    def test_a_clean_pr_or_one_with_no_approval_is_not_told_behind(self) -> None:
        """Clean and approved is ready to merge; behind and not approved is not told."""
        rounds = [*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED]
        clean = sweep(world_with(rounds)).out
        unapproved = sweep(
            world_with(TWO_PLAN_REJECTIONS, mergeable_state="behind")
        ).out
        assert_that(
            ["BEHIND:" in clean, "BEHIND:" in unapproved], equal_to([False] * 2)
        )

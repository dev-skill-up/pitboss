"""A green PR that is behind the base says BEHIND, with no merge offer (pitboss#369)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .test_commands import sweep
from .test_flow_sweep import EXECUTION_APPROVED, TWO_PLAN_REJECTIONS, world_with

LINE = (
    "BEHIND: update the branch, then the merge-main proof (bats merge-proof)"
    " is the review"
)


class TestBehind(unittest.TestCase):
    """The line, for an approved green PR and for the nearest inputs."""

    def test_an_approved_green_pr_that_is_behind_gets_the_line_and_no_merge(
        self,
    ) -> None:
        """BEHIND before any merge offer; the body-head command is named."""
        rounds = [*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED]
        swept = sweep(world_with(rounds, mergeable_state="behind")).out
        assert_that(swept, contains_string(LINE))
        assert_that("READY TO MERGE" in swept, equal_to(False))
        assert_that(swept, contains_string("pitboss body-head owner/project#3"))

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

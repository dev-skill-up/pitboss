"""I32 and the other cases about what ``slots next`` prints (pitboss#444).

Case 32: ``slots next --force --step review ITEM`` prints the review brief of any
open PR and says in its first line that it is forced.
"""

import unittest

from hamcrest import assert_that, starts_with

from . import world
from .cleanworld import same
from .itemworld import one, with_pull_issues
from .says import ended, says
from .rankworld import dependent_world

PULL = "owner/project#3"


class TestForcedReview(unittest.TestCase):
    """I32: the review brief for a PR whose step is not a review."""

    def test_i32_force_prints_the_review_brief_and_says_so_first(self) -> None:
        """A PR whose ticket waits has no step; forced, its review brief prints."""
        here = with_pull_issues(dependent_world())
        before = here.ledger.read_text()
        plain = one(here, PULL, "--step", "review")
        done = one(here, PULL, "--step", "review", "--force")
        same((plain.code, done.code, here.ledger.read_text() == before), (1, 0, True))
        assert_that(done.out, starts_with("FORCED REVIEW: owner/project#3 is at"))
        says(done.out, "review", "owner/project#3")

    def test_i32_force_refuses_what_it_cannot_review(self) -> None:
        """A repository not configured, and a ticket with no pull request."""
        here = with_pull_issues(world.make_world())
        for reference, why in (
            ("other/none#1", "other/none is not a configured repository"),
            ("owner/project#50", "UNKNOWN: owner/project#50 is not at the review"),
        ):
            done = one(here, reference, "--step", "review", "--force")
            ended(done, 1, "")
            says(done.err, why)

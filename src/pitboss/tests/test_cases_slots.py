"""I32 and the other cases about what ``slots next`` prints (pitboss#444).

Case 32: ``slots next --force --step review ITEM`` prints the review brief of any
open PR and says in its first line that it is forced.
"""

import unittest

from hamcrest import assert_that, equal_to, starts_with

from . import world
from .cleanworld import same
from .itemworld import one, with_pull_issues
from .says import says
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
        same(plain.code, 1)
        same(done.code, 0)
        assert_that(done.out, starts_with("FORCED REVIEW: owner/project#3 is at"))
        says(done.out, "review", "owner/project#3")
        same(here.ledger.read_text(), before)

    def test_i32_force_refuses_a_ticket_with_no_pull_request(self) -> None:
        """The nearest input it must still refuse: nothing to review."""
        here = with_pull_issues(world.make_world())
        done = one(here, "owner/project#50", "--step", "review", "--force")
        assert_that((done.code, done.out), equal_to((1, "")))
        says(done.err, "UNKNOWN: owner/project#50 is not at the review step")

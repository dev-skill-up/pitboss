"""A green pins-only PR whose pins-check prints OK is merged with no review.

pitboss#34 (keyword: pins-only): with OK the step is the merge, which the gate
decides (no regular review); any other output keeps the review.
"""

import unittest

from hamcrest import assert_that, equal_to

from . import actreviewed, fakes, world
from .pinsworld import OK_COMMAND, offered, ran_commands, relock, swept

REVIEW = "REVIEWER: owner/project#3: grade Plan and Execution together"
MERGE = actreviewed.MERGING.format(number=3)


class TestRelock(unittest.TestCase):
    """A relock PR at its review step."""

    def test_ok_is_ready_to_merge_with_no_review_line(self) -> None:
        """The command prints OK: the merge is the decision, no review."""
        here = relock(OK_COMMAND)
        assert_that(MERGE in swept(here), equal_to(True))
        assert_that(REVIEW in offered(here), equal_to(False))

    def test_the_command_runs_in_the_clone_after_fetching_the_head(self) -> None:
        """git fetches the base and the PR's head; env runs the command in the clone."""
        here = relock(OK_COMMAND)
        swept(here)
        clone = str(here.clone)
        fetch = ["git", "-C", clone, "fetch", "--quiet", "origin", "main"]
        fetched = [each for each in here.calls if each[: len(fetch)] == fetch]
        assert_that(fetched[0][-1], equal_to("pull/3/head"))
        assert_that(ran_commands(here)[0][2], equal_to(clone))

    def test_anything_but_ok_is_reviewed_as_before(self) -> None:
        """No OK last line, a failure or no head: the review stays."""
        missing = relock(OK_COMMAND)
        gone = ["update-ref", "-d", "refs/pull/3/head"]
        fakes.run_git(world.origin_of(missing.clone), *gone)
        cases = {
            "failure": relock("sh -c 'echo NOT-OK; exit 1'"),
            "exit zero": relock("echo NOT OK: x: behind"),
            "no fetch": missing,
        }
        for name, here in cases.items():
            with self.subTest(name):
                assert_that(MERGE in swept(here), equal_to(False))
                assert_that(REVIEW in offered(here), equal_to(True))

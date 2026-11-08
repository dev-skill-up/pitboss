"""A green pins-only PR whose pins-check prints OK is merged with no review.

pitboss#34 (keyword: pins-only): the sweep marks it ``PINS-ONLY OK``, offers no
review and offers the merge; any other output keeps the review.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, world
from .pinsworld import (
    OK_ANSWER,
    OK_COMMAND,
    offered,
    pins_lines,
    ran_commands,
    relock,
    swept,
)

REVIEW = "(review it"
MERGE = "READY TO MERGE owner/project#3"
OK_LINE = "PINS-ONLY OK owner/project#3: pins-check printed OK"
NOT_OK_LINE = "PINS-ONLY owner/project#3: pins-check did not print OK"


class TestRelock(unittest.TestCase):
    """A relock PR at its review step."""

    def test_ok_is_ready_to_merge_with_no_review_line(self) -> None:
        """The command prints OK: PINS-ONLY OK, READY TO MERGE, no review offered."""
        here = relock(OK_COMMAND)
        out = swept(here)
        said = f"{OK_LINE} ({OK_ANSWER}); no review is offered"
        assert_that(pins_lines(out), equal_to(said))
        assert_that(out, contains_string(MERGE))
        assert_that(offered(here), equal_to(""))

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
            "failure": (relock("sh -c 'echo NOT-OK; exit 1'"), "NOT-OK"),
            "exit zero": (relock("echo NOT OK: x: behind"), "NOT OK: x: behind"),
            "no fetch": (missing, "PINS-ONLY"),
        }
        for name, (here, said) in cases.items():
            with self.subTest(name):
                out = swept(here)
                assert_that(pins_lines(out), contains_string(said))
                assert_that(MERGE in out, equal_to(False))
                assert_that(offered(here), contains_string(REVIEW))
                assert_that(OK_LINE in out, equal_to(False))

    def test_a_line_says_why_it_was_not_ok(self) -> None:
        """The line starts with the marker and the pins-check's own words."""
        here = relock("echo NOT OK: bats.lock: behind")
        want = f"{NOT_OK_LINE} (NOT OK: bats.lock: behind); review it as before"
        assert_that(pins_lines(swept(here)), equal_to(want))

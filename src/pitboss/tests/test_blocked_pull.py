"""A PR whose ticket waits for an open ticket has no decision (pitboss#388).

The cause: a ticket with an open PR and a ``Depends on`` line was offered for a
review, a fix or a merge, and the ticket it waited for was not ranked with it.
"""

import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import rankworld, world
from .rankworld import dependent_world, starts, sweep

DEPENDENT_ORDER = [
    "owner/project#1",
    "owner/project#2",
    "owner/lib#3",
    "owner/lib#4",
    "owner/project#10",
]
KEPT_ORDER = [
    "owner/project#1",
    "owner/project#2",
    "owner/project#3",
    "owner/lib#4",
    "owner/project#10",
]
DECIDED = re.compile(r"^[A-Z]+: (owner/\S+#\d+):", re.MULTILINE)


def decided(out: str) -> Sequence[str]:
    """The items the sweep's pull request sections give a decision.

    Args:
        out: the sweep's output.

    Returns:
        Each decision line's item.
    """
    return DECIDED.findall(out)


class TestSlotsNext(unittest.TestCase):
    """What ``slots next`` offers for a PR whose ticket waits."""

    def test_the_blocker_stands_where_the_pull_request_stood(self) -> None:
        """No line for PR 3; the blocker is decided in its place (B10)."""
        assert_that(starts(dependent_world()), equal_to(DEPENDENT_ORDER))

    def test_the_blocker_is_closed(self) -> None:
        """PR 3 is decided in its own place, and the blocker is in no answer."""
        assert_that(starts(dependent_world("closed")), equal_to(KEPT_ORDER))

    def test_a_pull_request_with_no_round_is_in_no_answer(self) -> None:
        """PR 2 waits to be merged: it has no line, its blocker is in its place."""
        found = starts(dependent_world(pull=2))
        assert_that(
            found[:3], equal_to(["owner/project#1", "owner/lib#3", KEPT_ORDER[2]])
        )

    def test_the_suggestions_skip_the_blocked_pull_request(self) -> None:
        """``next`` suggests the blocker, never the PR."""
        out = rankworld.suggestions(dependent_world())
        assert_that(out, contains_string("start a PR: owner/lib#3:"))
        rankworld.absent(out, "owner/project#3:")

    def test_the_pull_request_that_fixes_the_blocker_is_the_blocker(self) -> None:
        """Ticket 11 is worked by PR 1: PR 1 is decided, 11 and PR 3 are not."""
        here = dependent_world()
        rankworld.ninth(here, "Depends on #11")
        eleven = rankworld.ticket("", number=11, labels=[])
        rankworld.serve(here, "owner/project", 11, eleven)
        rankworld.fixing(here, 1, "Fixes #11")
        wanted = [each for each in KEPT_ORDER if each != "owner/project#3"]
        assert_that(starts(here), equal_to(wanted))

    def test_a_pull_request_the_ticket_names_as_blocker_is_not_blocked(self) -> None:
        """Ticket 9 says it depends on PR 3, which fixes it: PR 3 keeps its step."""
        here = dependent_world()
        rankworld.ninth(here, "Depends on #3")
        assert_that(starts(here), equal_to(KEPT_ORDER))

    def test_a_closed_ticket_blocks_its_pull_request_no_more(self) -> None:
        """Ticket 9 is closed: whatever it says, PR 3 keeps its step."""
        here = dependent_world()
        rankworld.ninth(here, rankworld.DEPENDENT, "closed")
        assert_that(starts(here), equal_to(KEPT_ORDER))

    def test_a_ticket_that_cannot_be_read_blocks_nothing(self) -> None:
        """The API gives no answer for ticket 9, so PR 3 keeps its step."""
        here = dependent_world()
        del here.bodies[f"{world.PROJECT}/issues/9"]
        assert_that(starts(here), equal_to(KEPT_ORDER))

    def test_the_comments_of_the_ticket_are_read(self) -> None:
        """A member's comment on ticket 9 says it is blocked."""
        here = dependent_world()
        rankworld.ninth(here, "", comments=1)
        said = rankworld.comment(rankworld.DEPENDENT)
        here.bodies[rankworld.COMMENTS] = [said]
        assert_that(starts(here), equal_to(DEPENDENT_ORDER))


class TestSweep(unittest.TestCase):
    """The sweep decides the same, with the PR."""

    def test_the_pull_request_has_no_decision_while_its_ticket_waits(self) -> None:
        """PR 2 is decided, until its ticket waits: then it has no line."""
        closed = decided(sweep(dependent_world("closed", 2)).out)
        waiting = decided(sweep(dependent_world(pull=2)).out)
        assert_that(
            ["owner/project#2" in closed, "owner/project#2" in waiting],
            equal_to([True, False]),
        )

    def test_a_blocked_pull_request_has_no_fix_line(self) -> None:
        """PR 1 conflicts and is red; while its ticket waits, no step is printed."""
        out = sweep(dependent_world(pull=1)).out
        assert_that("owner/project#1" in decided(out), equal_to(False))

    def test_the_blocker_is_counted_as_queued_work(self) -> None:
        """The sweep's order has the blocker in the PR's place."""
        out = sweep(dependent_world()).out
        assert_that(rankworld.NEXT_LINE.findall(out), equal_to(DEPENDENT_ORDER))

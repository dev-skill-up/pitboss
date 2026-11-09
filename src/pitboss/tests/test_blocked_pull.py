"""A PR whose ticket waits for an open ticket has no step (pitboss#388).

The cause: a ticket with an open PR and a ``Depends on`` line was offered for a
review, a fix or a merge, and the ticket it waited for was not ranked with it.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import rankworld, world
from .rankworld import (
    dependent_world,
    lines_are,
    next_output,
    printed,
    starts,
    sweep,
)

BLOCKED_PULL = "BLOCKED owner/project#3 by owner/lib#3"
BLOCKS_LINE = (
    "BLOCKS owner/lib#3: blocks owner/project#3; ranked urgent, opened 2026-09-01"
)
READY = "READY TO MERGE owner/project#2"


class TestSlotsNext(unittest.TestCase):
    """What ``slots next`` offers for a PR whose ticket waits."""

    def test_the_blocker_stands_where_the_pull_request_stood(self) -> None:
        """No line for PR 3; the blocker is listed where its review would be."""
        here = dependent_world()
        assert_that(
            starts(here),
            equal_to(["owner/project#1", "owner/lib#3", "owner/project#10"]),
        )
        output = next_output(here)
        lines_are(output, "BLOCKED", [BLOCKED_PULL])
        lines_are(output, "BLOCKS", [BLOCKS_LINE])
        rankworld.absent(output, "PR STATE owner/project#3")

    def test_the_blocker_is_closed(self) -> None:
        """The PR line is back, the blocker has none, and nothing is blocked."""
        here = dependent_world("closed")
        assert_that(
            starts(here),
            equal_to(["owner/project#1", "owner/project#3", "owner/project#10"]),
        )
        output = next_output(here)
        lines_are(output, "BLOCKED", [])
        lines_are(output, "BLOCKS", [])
        assert_that(output, contains_string("PR STATE owner/project#3"))

    def test_a_younger_blocker_is_ranked_by_the_dependent_age(self) -> None:
        """The blocker was opened on 2026-09-09; its line says 2026-09-01."""
        output = next_output(dependent_world())
        assert_that(
            output,
            contains_string("owner/lib#3 (start a PR urgent, opened 2026-09-01,"),
        )

    def test_a_pull_request_with_no_round_is_listed_blocked(self) -> None:
        """PR 2 waits to be merged: its merge is not offered, its blocker is."""
        here = dependent_world(pull=2)
        output = next_output(here)
        blocked = "BLOCKED owner/project#2 by owner/lib#3"
        lines_are(output, "BLOCKED", [blocked])
        assert_that(
            starts(here),
            equal_to(
                [
                    "owner/project#1",
                    "owner/project#3",
                    "owner/lib#3",
                    "owner/project#10",
                ]
            ),
        )

    def test_the_suggestions_skip_the_blocked_pull_request(self) -> None:
        """``next`` suggests the blocker, never the review of the PR."""
        here = dependent_world()
        out = rankworld.suggestions(here)
        assert_that(out, contains_string("start a PR: owner/lib#3:"))
        rankworld.absent(out, "owner/project#3 at head")

    def test_the_pull_request_that_fixes_the_blocker_is_the_blocker(self) -> None:
        """Ticket 11 is worked by PR 1: PR 1 stands for it, and nothing is added."""
        here = dependent_world()
        rankworld.ninth(here, "Depends on #11")
        eleven = rankworld.ticket("", number=11, labels=[])
        rankworld.serve(here, "owner/project", 11, eleven)
        rankworld.fixing(here, 1, "Fixes #11")
        assert_that(starts(here), equal_to(["owner/project#1", "owner/project#10"]))
        output = next_output(here)
        blocked = "BLOCKED owner/project#3 by owner/project#11"
        lines_are(output, "BLOCKED", [blocked])
        blocks = (
            "BLOCKS owner/project#1: blocks owner/project#3;"
            " ranked with the oldest of them"
        )
        lines_are(output, "BLOCKS", [blocks])

    def test_a_pull_request_the_ticket_names_as_blocker_is_not_blocked(self) -> None:
        """Ticket 9 says it depends on PR 3, which fixes it: PR 3 keeps its step."""
        here = dependent_world()
        rankworld.ninth(here, "Depends on #3")
        assert_that(starts(here)[1], equal_to("owner/project#3"))
        printed(here, "BLOCKED", [])

    def test_a_closed_ticket_blocks_its_pull_request_no_more(self) -> None:
        """Ticket 9 is closed: whatever it says, PR 3 keeps its step."""
        here = dependent_world()
        rankworld.ninth(here, rankworld.DEPENDENT, "closed")
        assert_that(starts(here)[1], equal_to("owner/project#3"))

    def test_a_ticket_that_cannot_be_read_blocks_nothing(self) -> None:
        """The API gives no answer for ticket 9, so PR 3 keeps its step."""
        here = dependent_world()
        del here.bodies[f"{world.PROJECT}/issues/9"]
        assert_that(starts(here)[1], equal_to("owner/project#3"))

    def test_the_comments_of_the_ticket_are_read(self) -> None:
        """A member's comment on ticket 9 says it is blocked."""
        here = dependent_world()
        rankworld.ninth(here, "", comments=1)
        said = rankworld.comment(rankworld.DEPENDENT)
        here.bodies[rankworld.COMMENTS] = [said]
        printed(here, "BLOCKED", [BLOCKED_PULL])


class TestSweep(unittest.TestCase):
    """The sweep prints the same, with the PR."""

    def test_the_line_stands_in_place_of_the_merge(self) -> None:
        """PR 2 is ready to merge, until its ticket waits: then BLOCKED, once."""
        assert_that(sweep(dependent_world("closed", 2)).out, contains_string(READY))
        out = sweep(dependent_world(pull=2)).out
        blocked = "BLOCKED owner/project#2 by owner/lib#3"
        lines_are(out, "BLOCKED", [blocked])
        rankworld.absent(out, READY)

    def test_a_blocked_pull_request_has_no_fix_line(self) -> None:
        """PR 1 conflicts and is red; while its ticket waits, no step is printed."""
        out = sweep(dependent_world(pull=1)).out
        rankworld.absent(out, "CONFLICT owner/project#1")
        rankworld.absent(out, "FAILED owner/project#1")
        blocked = "BLOCKED owner/project#1 by owner/lib#3"
        lines_are(out, "BLOCKED", [blocked])

    def test_the_blocker_is_counted_as_queued_work(self) -> None:
        """The sweep prints the BLOCKS line once and the blocker is queued."""
        out = sweep(dependent_world()).out
        lines_are(out, "BLOCKS", [BLOCKS_LINE])
        lines_are(out, "BLOCKED", [BLOCKED_PULL])
        assert_that(out, contains_string("SLOTS FREE 1: 3 queued"))

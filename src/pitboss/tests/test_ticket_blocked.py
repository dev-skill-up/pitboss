"""A ticket that says it cannot be worked on until a ticket is closed (pitboss#163).

The cause: bats-lang/pwa#279, repository-prototype#568 and quire#1045 each said
"Cannot be worked on until bats-lang/repository-prototype#567 has merged" and
``slots next`` listed them as ready p0 tickets, so an orchestrator skipped them
by hand.
"""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config, ticketblock
from . import fakes, world
from .test_commands import sweep
from .test_holds import START_LINE
from .test_slot_commands import next_output

ISSUES = "/".join((world.PROJECT, "issues"))
LIST = fakes.page(ISSUES + "?state=open&labels=urgent")
COMMENTS = fakes.page(ISSUES + "/9/comments")
FUTURE = world.FUTURE
BLOCKER = "repos/owner/lib/issues/3"
LATER = {**world.TICKET, "number": 10, "created_at": "2026-09-02T00:00:00+00:00"}
SENTENCE = "Cannot be worked on until owner/lib#3 has merged"
BLOCKED_LINE = re.compile(r"^BLOCKED \S+#\d+ by .*$", re.MULTILINE)
REPOSITORY = config.make_repo("owner", "project")


def blocked_world(
    body: str = SENTENCE,
    state: str = "open",
    comments: Sequence[Mapping[str, str]] = (),
) -> world.World:
    """A world with ticket 9 that names a blocker, and a later ticket 10.

    Args:
        body: the body of ticket 9.
        state: the state of owner/lib#3.
        comments: the comments of ticket 9.

    Returns:
        The world.
    """
    here = world.make_world()
    ticket = {**world.TICKET, "body": body, "comments": len(comments)}
    here.bodies[LIST] = [ticket, LATER]
    here.bodies[COMMENTS] = list(comments)
    here.bodies[BLOCKER] = {"state": state, "labels": []}
    return here


def comment(body: str, association: str = "MEMBER") -> Mapping[str, str]:
    """A comment on ticket 9.

    Args:
        body: its text.
        association: its author's association.

    Returns:
        The JSON of the comment.
    """
    return {
        "body": body,
        "author_association": association,
        "created_at": "2026-09-03T00:00:00Z",
    }


def offered(here: world.World) -> Sequence[str]:
    """The tickets ``slots next`` lists.

    Args:
        here: the world.

    Returns:
        Their references, in the order listed.
    """
    return START_LINE.findall(next_output(here))


class TestSentence(unittest.TestCase):
    """The tickets a text says it cannot be worked on until."""

    def test_the_forms(self) -> None:
        """Both sentences, any case, with a full or a bare reference."""
        cases = {
            SENTENCE: ["owner/lib#3"],
            "cannot be worked on until #4": ["owner/project#4"],
            "Blocked by owner/lib#5 and by lib#6": ["owner/lib#5"],
            "blocked  by\nowner/lib#7": ["owner/lib#7"],
            "this ticket is not blocked": [],
            "see owner/lib#3": [],
        }
        for text, expected in cases.items():
            with self.subTest(text):
                assert_that(
                    list(ticketblock.named(text, REPOSITORY)), equal_to(expected)
                )


class TestSlotsNext(unittest.TestCase):
    """What ``slots next`` offers while the blocker is open, then closed."""

    def test_the_blocker_is_open(self) -> None:
        """The blocked ticket has no NEXT line, and a BLOCKED line."""
        here = blocked_world()
        assert_that(offered(here), equal_to(["owner/project#10"]))
        found = BLOCKED_LINE.findall(next_output(here))
        assert_that(found, equal_to(["BLOCKED owner/project#9 by owner/lib#3"]))

    def test_the_blocker_is_closed(self) -> None:
        """The ticket is listed in its place in the order, with no BLOCKED line."""
        here = blocked_world(state="closed")
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))
        assert_that(BLOCKED_LINE.findall(next_output(here)), equal_to([]))

    def test_the_open_then_closed_order_differs_only_by_the_ticket(self) -> None:
        """Closing the blocker changes the list by that ticket alone."""
        here = blocked_world()
        before = offered(here)
        here.bodies[BLOCKER] = {"state": "closed", "labels": []}
        assert_that(offered(here)[1:], equal_to(before))

    def test_a_merged_pull_request_blocks_nothing(self) -> None:
        """A PR that merged reads as closed."""
        here = blocked_world(state="closed")
        here.bodies[BLOCKER] = {"state": "closed", "labels": [], "merged": True}
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))

    def test_blocked_by_in_a_trusted_comment(self) -> None:
        """A comment of a member counts, as the body does."""
        here = blocked_world("A ticket", comments=[comment("Blocked by owner/lib#3")])
        assert_that(offered(here), equal_to(["owner/project#10"]))
        assert_that(len(BLOCKED_LINE.findall(next_output(here))), equal_to(1))

    def test_a_comment_of_a_stranger_does_not_count(self) -> None:
        """Only the trusted authors' comments are read."""
        stranger = comment("Blocked by owner/lib#3", "NONE")
        here = blocked_world("A ticket", comments=[stranger])
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))

    def test_a_blocker_that_cannot_be_read_blocks_nothing(self) -> None:
        """The API gives no answer for the blocker, so the ticket is offered."""
        here = blocked_world()
        del here.bodies[BLOCKER]
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))

    def test_the_suggestions_skip_it(self) -> None:
        """``next`` suggests the ticket that is not blocked."""
        here = blocked_world()
        suggested = re.findall(
            r"start a PR: (\S+#\d+):", world.again(here, "next", "--now", FUTURE).out
        )
        assert_that(suggested, equal_to(["owner/project#10"]))


class TestSweep(unittest.TestCase):
    """The sweep prints the same line."""

    def test_the_line(self) -> None:
        """The BLOCKED line is in the sweep while the blocker is open."""
        found = BLOCKED_LINE.findall(sweep(blocked_world()).out)
        assert_that(found, equal_to(["BLOCKED owner/project#9 by owner/lib#3"]))

    def test_no_line_when_closed(self) -> None:
        """Closed, the ticket has no line."""
        out = sweep(blocked_world(state="closed")).out
        assert_that(BLOCKED_LINE.findall(out), equal_to([]))

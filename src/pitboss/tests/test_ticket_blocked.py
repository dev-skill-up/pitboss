"""A ticket that says it cannot be worked on until a ticket is closed (pitboss#163).

The cause: bats-lang/pwa#279, repository-prototype#568 and quire#1045 each said
"Cannot be worked on until bats-lang/repository-prototype#567 has merged" and
``slots next`` listed them as ready p0 tickets, so an orchestrator skipped them
by hand.
"""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import (
    assert_that,
    contains_string,
    equal_to,
    has_length,
)

from .. import brief, ticketblock
from . import briefmake, decisionline, fakes, liveagents, quietworld, rankworld, world
from .test_commands import sweep
from .test_holds import START_LINE
from .test_slot_commands import next_output

ISSUES = rankworld.ISSUES
LIST = rankworld.LIST
COMMENTS = rankworld.COMMENTS
FUTURE = world.FUTURE
BLOCKER = rankworld.BLOCKER
LATER = rankworld.LATER
SENTENCE = "Cannot be worked on until owner/lib#3 has merged"
BLOCKED_LINE = re.compile(r"^BLOCKED \S+#\d+ by .*$", re.MULTILINE)
REPOSITORY = rankworld.REPOSITORY


blocked_world = rankworld.blocked_world
comment = rankworld.comment


def unsaid(here: world.World, *tickets: str) -> bool:
    """Whether ``slots next`` says nothing of the tickets that wait (keyword: one-path).

    Args:
        here: the world.
        *tickets: the waiting tickets.

    Returns:
        True when no line is a BLOCKED line and none is a decision of one of them.
    """
    printed = next_output(here)
    decided = [decisionline.of(printed, each) for each in tickets]
    return BLOCKED_LINE.findall(printed) == [] and decided == [""] * len(tickets)


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
        """The ticket waits, with no line; its blocker is offered (#280)."""
        here = blocked_world()
        assert_that(offered(here), equal_to(["owner/lib#3", "owner/project#10"]))
        assert_that(unsaid(here, "owner/project#9"), equal_to(True))

    def test_the_blocker_is_closed(self) -> None:
        """The ticket is listed in its place in the order."""
        here = blocked_world(state="closed")
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))

    def test_the_open_then_closed_order_differs_only_by_the_ticket(self) -> None:
        """Closing the blocker swaps the blocker's line for the ticket's."""
        here = blocked_world()
        before = offered(here)
        here.bodies[BLOCKER] = {"state": "closed", "labels": []}
        assert_that(offered(here)[1:], equal_to(before[1:]))
        assert_that(before[0], equal_to("owner/lib#3"))

    def test_a_merged_pull_request_blocks_nothing(self) -> None:
        """A PR that merged reads as closed."""
        here = blocked_world(state="closed")
        here.bodies[BLOCKER] = {"state": "closed", "labels": [], "merged": True}
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))

    def test_blocked_by_in_a_trusted_comment(self) -> None:
        """A comment of a member counts, as the body does."""
        here = blocked_world("A ticket", comments=[comment("Blocked by owner/lib#3")])
        assert_that(offered(here), equal_to(["owner/lib#3", "owner/project#10"]))
        assert_that(unsaid(here, "owner/project#9"), equal_to(True))

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
        """``next`` suggests the blocker and the ticket that is not blocked."""
        here = blocked_world()
        live = liveagents.running(here)
        suggested = re.findall(
            r"start a PR: (\S+#\d+):",
            world.again(here, "next", "--now", FUTURE, *live).out,
        )
        assert_that(suggested, equal_to(["owner/lib#3", "owner/project#10"]))


# pitboss#280: bats-lang/quire#830 said "Depends on #828" and was offered as NEXT 2;
# a worker was started on it and handed back NOT STARTED, a round lost, although the
# ticket it waited for was the work to do.
THIRD = {**world.TICKET, "number": 11, "created_at": "2026-09-03T00:00:00+00:00"}
DEPENDS = "Depends on owner/lib#3"
LIB_THREE = rankworld.LIB_THREE


def depends_world(body: str = DEPENDS) -> world.World:
    """Ticket 9 depends on an open ticket that has no priority label.

    Args:
        body: the body of ticket 9.

    Returns:
        The world.
    """
    return rankworld.depends_world(body)


def serve_ticket(here: world.World, number: int, found: Mapping[str, object]) -> None:
    """Make the fake GitHub answer for a ticket of the project.

    Args:
        here: the world.
        number: the ticket's number.
        found: the JSON of the ticket.
    """
    here.bodies[f"{world.PROJECT}/issues/{number}"] = dict(found)


def add_label(here: world.World, label: str, tickets: Sequence[object]) -> None:
    """Add a priority label after urgent, with the project's tickets under it.

    Args:
        here: the world.
        label: the label.
        tickets: the project's open tickets with it.
    """
    quietworld.edit_config(
        here, 'priority_labels = ["urgent"', f'priority_labels = ["urgent", "{label}"'
    )
    served = {world.PROJECT: list(tickets), world.LIBRARY: []}
    for repository, found in served.items():
        here.bodies[fakes.page(f"{repository}/issues?state=open&labels={label}")] = (
            found
        )


class TestForm(unittest.TestCase):
    """The sentence that names a dependency."""

    def test_depends_on(self) -> None:
        """Any case, with or without a colon, a full or a bare reference."""
        cases = {
            DEPENDS: ["owner/lib#3"],
            "depends on #828": ["owner/project#828"],
            "DEPENDS ON: #4": ["owner/project#4"],
            "Depends\non\nowner/lib#5": ["owner/lib#5"],
        }
        for text, expected in cases.items():
            with self.subTest(text):
                found = ticketblock.named(text, REPOSITORY)
                assert_that(list(found), equal_to(expected))

    def test_other_words_name_nothing(self) -> None:
        """The nearest texts that are not the sentence."""
        for text in ("independent of #3", "depend on #3", "depends upon #3"):
            with self.subTest(text):
                assert_that(list(ticketblock.named(text, REPOSITORY)), equal_to([]))


class TestOrder(unittest.TestCase):
    """What ``slots next`` and the sweep offer while the dependency is open."""

    def test_an_unlabelled_dependency_takes_the_place_of_the_ticket(self) -> None:
        """NEXT for the dependency, ahead of ticket 10, and none for ticket 9."""
        here = depends_world()
        assert_that(offered(here), equal_to(["owner/lib#3", "owner/project#10"]))
        assert_that(unsaid(here, "owner/project#9"), equal_to(True))

    def test_a_dependency_listed_later_is_moved_ahead(self) -> None:
        """Ticket 9 depends on 11 (label later), which is listed after ticket 10."""
        here = blocked_world("Depends on #11")
        nine = {**world.TICKET, "body": "Depends on #11"}
        here.bodies[LIST] = [nine, LATER]
        add_label(here, "later", [{**THIRD, "labels": [{"name": "later"}]}])
        serve_ticket(here, 11, {"state": "open", "labels": []})
        assert_that(offered(here), equal_to(["owner/project#11", "owner/project#10"]))

    def test_the_sweep_offers_the_same(self) -> None:
        """The sweep's list has the dependency, and nothing of the ticket."""
        here = depends_world()
        here.bodies[LIST] = [{**world.TICKET, "body": DEPENDS}]
        out = sweep(here).out
        assert_that(decisionline.of(out, "owner/lib#3"), contains_string("WORKER"))
        assert_that(decisionline.of(out, "owner/project#9"), equal_to(""))
        assert_that(BLOCKED_LINE.findall(out), equal_to([]))

    def test_a_dependency_of_a_dependency_is_offered(self) -> None:
        """Ticket 9 waits for lib#3, which waits for lib#7: lib#7 is the work."""
        here = depends_world()
        here.bodies[BLOCKER] = {**LIB_THREE, "body": "Depends on owner/lib#7"}
        here.bodies["repos/owner/lib/issues/7"] = {
            **LIB_THREE,
            "title": "The root",
            "body": "",
        }
        assert_that(offered(here), equal_to(["owner/lib#7", "owner/project#10"]))
        assert_that(unsaid(here, "owner/lib#3", "owner/project#9"), equal_to(True))

    def test_a_cycle_offers_neither(self) -> None:
        """Two tickets that depend on each other are both blocked."""
        here = blocked_world("Depends on #10")
        nine = {**world.TICKET, "body": "Depends on #10"}
        ten = {**LATER, "body": "Depends on #9"}
        here.bodies[LIST] = [nine, ten]
        serve_ticket(here, 10, {"state": "open", "labels": [], "body": ten["body"]})
        serve_ticket(here, 9, {"state": "open", "labels": [], "body": nine["body"]})
        assert_that(offered(here), has_length(0))

    def test_a_pull_request_is_not_listed_as_a_ticket(self) -> None:
        """A PR is worked as a PR; the ticket that waits for it is not offered."""
        here = depends_world()
        here.bodies[BLOCKER] = {**LIB_THREE, "pull_request": {}}
        assert_that(offered(here), equal_to(["owner/project#10"]))

    def test_a_closed_dependency_changes_nothing(self) -> None:
        """The ticket is listed in its place, and the dependency is not."""
        here = depends_world()
        here.bodies[BLOCKER] = {**LIB_THREE, "state": "closed"}
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))

    def test_a_dependency_that_cannot_be_read_is_not_offered(self) -> None:
        """Unreadable, it blocks nothing and joins nothing."""
        here = depends_world()
        del here.bodies[BLOCKER]
        assert_that(offered(here), equal_to(["owner/project#9", "owner/project#10"]))

    def test_the_suggestion_starts_the_dependency(self) -> None:
        """``next`` suggests the dependency first, and its brief has the rule."""
        here = depends_world()
        out = rankworld.suggestions(here)
        suggested = re.findall(r"start a PR: (\S+#\d+):", out)
        assert_that(suggested, equal_to(["owner/lib#3", "owner/project#10"]))
        assert_that(out, contains_string("is never ground for a split"))


class TestBrief(unittest.TestCase):
    """What a worker is told about a dependency."""

    def test_a_new_pr_brief_says_a_dependency_is_never_ground_for_a_split(self) -> None:
        """The start-a-PR text."""
        briefmake.pinned(
            brief.Kind.NEW_PR,
            [
                "a ticket that depends on another open ticket is not impossible in"
                " one PR and is never ground for a split",
                "name the ticket it waits for",
                "the orchestrator does that ticket first",
            ],
        )

"""``slots next ITEM``: the item's decision, or the list's (keyword: one-path).

The item forms print the item's decision when it has one, and otherwise the same
answer as the list, with nothing about the item (the one-path plan, section 6.2).
A read that fails ends the command: no decision on a partial world.
"""

import unittest
from typing import Callable, Sequence

from hamcrest import assert_that, equal_to

from . import quietworld, rankworld, test_flow_sweep, test_holds, world
from .fastvariants import closed, named, superseded, waiting
from .fastworld import NINTH, fast_world, listed, prepared
from .itemworld import one, with_pull_issues
from .says import read_failed

STARTS = "WORKER: owner/project#9: write the code"


def decided(here: world.World, reference: str, line: str) -> None:
    """Require the item's decision first, with a status of 0.

    Args:
        here: the world.
        reference: the item.
        line: how its decision starts.
    """
    found = one(here, reference)
    assert_that(found.code, equal_to(0))
    assert_that(found.out.startswith(line), equal_to(True))


def held() -> world.World:
    """A world where the owner holds new pull requests of the project.

    Returns:
        The world.
    """
    return prepared(test_holds.held_world(test_holds.PROJECT_TABLE))


def at_a_wait() -> world.World:
    """A world where PR 3 is a draft whose rounds disagree after the ruling.

    Returns:
        The world.
    """
    flow = test_flow_sweep
    rounds = flow.RULED + [flow.graded(flow.CHANGES, None, 4)]
    return with_pull_issues(flow.world_with(rounds, draft=True))


class TestADecision(unittest.TestCase):
    """An item that has a decision prints it."""

    def test_a_ticket_prints_its_decision(self) -> None:
        """Ticket 9 is started by a worker."""
        decided(fast_world(), NINTH, STARTS)

    def test_a_ticket_the_owner_ranks_needs_no_label(self) -> None:
        """The owner's stated priority is its rank, whatever labels it has."""
        here = fast_world()
        rankworld.serve(here, "owner/project", 9, rankworld.ticket(labels=[]))
        stated = '[slots.owner_priorities]\n"owner/project#9" = "urgent"\n[slots]'
        quietworld.edit_config(here, "[slots]", stated)
        decided(here, NINTH, STARTS)

    def test_a_named_ticket_is_examined_with_no_label(self) -> None:
        """Ticket 50 is in no listing walked; named, it is examined."""
        here = with_pull_issues(world.make_world())
        decided(here, "owner/project#50", "WORKER: owner/project#50: write the code")

    def test_a_pull_request_prints_its_decision(self) -> None:
        """PR 1 is at a conflict, PR 3 at a pause for the owner."""
        decided(
            with_pull_issues(world.make_world()),
            "owner/project#1",
            "WORKER: owner/project#1: resolve the conflict",
        )
        paused = "ORCHESTRATOR: owner/project#3: label the PR and its ticket paused"
        decided(at_a_wait(), "owner/project#3", paused)


Build = Callable[[], world.World]
NO_DECISION: Sequence[tuple[Build, str]] = [
    (closed, NINTH),
    (named, NINTH),
    (held, NINTH),
    (waiting, NINTH),
    (superseded, NINTH),
    (rankworld.dependent_world, "owner/project#3"),
]


class TestNoDecision(unittest.TestCase):
    """An item with no decision prints the list's answer, with nothing about it."""

    def test_the_list_is_printed_and_the_item_is_not_named(self) -> None:
        """A closed ticket, one a PR fixes, a hold, a blocker, the superseded."""
        for build, reference in NO_DECISION:
            with self.subTest(build.__name__, reference=reference):
                here = with_pull_issues(build())
                found = one(here, reference)
                assert_that(found.code, equal_to(0))
                assert_that(f": {reference}:" in found.out, equal_to(False))
                whole = rankworld.NEXT_LINE.findall(listed(here).out)
                assert_that(rankworld.NEXT_LINE.findall(found.out), equal_to(whole))


class TestAFailedRead(unittest.TestCase):
    """A read that fails ends the command with no decision."""

    def test_an_unreadable_pull_request_ends_the_command(self) -> None:
        """PR 1's checks cannot be read: status 1, the request on standard error."""
        here = with_pull_issues(world.make_world())
        world.unread_first(here)
        read_failed(one(here, "#1"))

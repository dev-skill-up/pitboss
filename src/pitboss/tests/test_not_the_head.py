"""``next TICKET`` says when its ticket is not the head of the queue (pitboss#415)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from . import fakes, quietworld, world
from .rankworld import publish
from .ownerbodies import lines_of

TEN = "owner/project#10"
TWELVE = "owner/project#12"
RANKS = ["p0", "p1", "p2", "p3"]
QUEUE = {9: ("p3", "open"), 10: ("p1", "open"), 12: ("p0", "open")}


def next_for(here: world.World, ticket: str) -> world.Result:
    """Run ``pitboss next`` for a ticket.

    Args:
        here: the world.
        ticket: the ticket.

    Returns:
        What it did.
    """
    return world.invoke(
        here, "next", "--config", here.config, ticket, "--now", world.FUTURE
    )


def queued() -> world.World:
    """A world whose tickets are a p3, a p1 and a p0.

    Returns:
        The world.
    """
    return fill(world.make_world(), QUEUE)


def fill(here: world.World, tickets: Mapping[int, tuple[str, str]]) -> world.World:
    """Give a world these tickets and no open PR.

    Args:
        here: the world.
        tickets: each ticket's number, label and state.

    Returns:
        The world.
    """
    quietworld.edit_config(here, '["urgent"]', str(RANKS).replace("'", '"'))
    publish(here, RANKS, tickets)
    for slug in (world.PROJECT, world.LIBRARY):
        here.bodies[fakes.page(f"{slug}/pulls?state=open")] = []
    return here


class TestNotTheHead(unittest.TestCase):
    """A p0 filed after a p1 listing takes the head."""

    def test_the_p1_ticket_is_told_the_head_is_the_p0(self) -> None:
        """The first line names the rank, the head and its brief command."""
        here = queued()
        first = next_for(here, TEN).out.splitlines()[0]
        assert_that(
            first,
            equal_to(
                f"NOT THE HEAD: {TEN} is rank 2; the head is {TWELVE} (p0, opened"
                f" 2026-09-04); its brief: pitboss slots next {TWELVE}"
                f" --config {here.config}"
            ),
        )

    def test_the_head_gets_no_such_line(self) -> None:
        """The output of the head is unchanged."""
        here = queued()
        assert_that(lines_of(next_for(here, TWELVE).out, "NOT THE HEAD"), equal_to([]))

    def test_a_ticket_outside_the_order_gets_no_such_line(self) -> None:
        """A ticket the list does not offer has no rank to compare."""
        here = queued()
        found = next_for(here, "owner/project#99").out
        assert_that(lines_of(found, "NOT THE HEAD"), equal_to([]))

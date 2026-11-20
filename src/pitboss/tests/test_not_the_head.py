"""``next TICKET`` prints the ticket's decision, wherever it ranks (pitboss#415)."""

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
    """An item form prints the item's decision, with no line about the head.

    ``NOT THE HEAD`` is retired (keyword: one-path, 6.2): the item form prints its
    decision, and the list is where the order is said.
    """

    def test_the_p1_ticket_prints_its_own_decision(self) -> None:
        """The first line is ticket 10's decision; nothing names the head."""
        out = next_for(queued(), TEN).out
        first = out.splitlines()[0]
        assert_that(first.startswith(f"WORKER: {TEN}: write the code"), equal_to(True))
        assert_that(lines_of(out, "NOT THE HEAD"), equal_to([]))

    def test_the_head_prints_its_own_decision(self) -> None:
        """The head's item form is its decision too."""
        first = next_for(queued(), TWELVE).out.splitlines()[0]
        wanted = f"WORKER: {TWELVE}: write the code"
        assert_that(first.startswith(wanted), equal_to(True))

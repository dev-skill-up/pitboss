"""``next TICKET`` says when its ticket is not the head of the queue (pitboss#415)."""

import unittest

from hamcrest import assert_that, equal_to

from . import world
from .test_owner_repositories import lines_of
from .test_slots_next_item import ALL, TEN, priorities

TWELVE = "owner/project#12"
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


class TestNotTheHead(unittest.TestCase):
    """A p0 filed after a p1 listing takes the head."""

    def test_the_p1_ticket_is_told_the_head_is_the_p0(self) -> None:
        """The first line names the rank, the head and its brief command."""
        here = priorities(ALL, {}, QUEUE)
        first = next_for(here, TEN).out.splitlines()[0]
        assert_that(
            first,
            equal_to(
                f"NOT THE HEAD: {TEN} is rank 2; the head is {TWELVE} (p0, opened"
                f" 2026-09-01); its brief: pitboss slots next {TWELVE} --config {here.config}"
            ),
        )

    def test_the_head_gets_no_such_line(self) -> None:
        """The output of the head is unchanged."""
        here = priorities(ALL, {}, QUEUE)
        assert_that(lines_of(next_for(here, TWELVE).out, "NOT THE HEAD"), equal_to([]))

    def test_a_ticket_outside_the_order_is_said_so(self) -> None:
        """A ticket the list does not offer has no rank."""
        here = priorities(ALL, {}, QUEUE)
        first = next_for(here, "owner/project#99").out.splitlines()[0]
        assert_that(
            first.startswith("NOT THE HEAD: owner/project#99 is not in the order;"),
            equal_to(True),
        )

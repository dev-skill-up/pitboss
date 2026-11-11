"""Why an item is not in the order of ``slots next`` (keyword: unqueued)."""

import dataclasses
import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import unqueued, work
from . import fakes, rankworld, world
from .itemworld import one, with_pull_issues
from .says import says


def offer(*blocked: work.Item) -> work.Offered:
    """An offer that keeps some items back.

    Args:
        *blocked: the items with blockers.

    Returns:
        The offer.
    """
    return work.Offered(items=[], held=[], standing={}, blocked=blocked)


def waits(reference: str, *blockers: str) -> work.Item:
    """An item that waits for blockers.

    Args:
        reference: the item.
        *blockers: what it waits for.

    Returns:
        The item.
    """
    return work.Item(
        category=work.Category.NEW_PR,
        reference=reference,
        created_at="2026",
        title="t",
        blockers=blockers,
    )


def said_of(found: Mapping[str, object], held: work.Offered) -> str:
    """What is said of ``o/b#2`` when the API gives a ticket.

    Args:
        found: the ticket's JSON.
        held: the offer.

    Returns:
        The phrase.
    """
    api = fakes.github({"repos/o/b/issues/2": dict(found)})
    return unqueued.why(api, held, "o/b#2")


class TestWaiting(unittest.TestCase):
    """The items that wait for a ticket."""

    def test_a_blocked_item_and_a_dependency_offered_ahead(self) -> None:
        """Each waiting item is named once, whichever way it was found."""
        both = offer(waits("o/a#1", "o/b#2"), waits("o/a#3", "o/b#2"))
        both = dataclasses.replace(both, blocks={"o/b#2": ["o/a#1", "o/a#4"]})
        found = unqueued.waiting(both, "o/b#2")
        assert_that(list(found), equal_to(["o/a#1", "o/a#4", "o/a#3"]))


class TestWhy(unittest.TestCase):
    """What is said of an item that is not queued."""

    def test_a_ticket_with_no_label_that_blocks_nothing(self) -> None:
        """The state, the labels and the items it blocks are named."""
        here = world.make_world()
        ticket = rankworld.ticket(labels=[], number=77)
        here.bodies.update({"repos/owner/project/issues/77": ticket})
        found = one(with_pull_issues(here), "owner/project#77")
        says(found.err, "state open, labels none, blocks no item")

    def test_a_closed_ticket_with_labels(self) -> None:
        """Its state and labels, and the item that waits for it."""
        closed = rankworld.ticket(state="closed", number=2)
        said = said_of(closed, offer(waits("o/a#1", "o/b#2")))
        expected = "it is a ticket, state closed, labels urgent, blocks o/a#1"
        assert_that(said, equal_to(expected))

    def test_a_pull_request(self) -> None:
        """A PR is said to be one."""
        said = said_of(rankworld.ticket(number=2, pull_request={}), offer())
        expected = "it is a PR, state open, labels urgent, blocks no item"
        assert_that(said, equal_to(expected))

    def test_an_item_that_cannot_be_read(self) -> None:
        """The API gives nothing."""
        said = unqueued.why(fakes.github({}), offer(), "o/b#2")
        assert_that(said, equal_to("it cannot be read"))

"""Why an item is not in the order of ``slots next`` (keyword: unqueued, pitboss#448)."""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import unqueued, work
from . import fakes, rankworld, test_item_fast
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
        here = test_item_fast.fast_world()
        found = rankworld.ticket(labels=[], number=77)
        rankworld.serve(here, "owner/project", 77, found)
        found = one(with_pull_issues(here), "owner/project#77")
        says(found.err, "state open, labels none, blocks no item")

    def test_a_closed_ticket_with_labels(self) -> None:
        """Its state and labels, and the item that waits for it."""
        api = fakes.github(
            {"repos/o/b/issues/2": rankworld.ticket(state="closed", number=2)}
        )
        said = unqueued.why(api, offer(waits("o/a#1", "o/b#2")), "o/b#2")
        expected = "it is a ticket, state closed, labels urgent, blocks o/a#1"
        assert_that(said, equal_to(expected))

    def test_a_pull_request(self) -> None:
        """A PR is said to be one."""
        api = fakes.github(
            {"repos/o/b/issues/2": rankworld.ticket(number=2, pull_request={})}
        )
        said = unqueued.why(api, offer(), "o/b#2")
        assert_that(
            said, equal_to("it is a PR, state open, labels urgent, blocks no item")
        )

    def test_an_item_that_cannot_be_read(self) -> None:
        """The API gives nothing."""
        said = unqueued.why(fakes.github({}), offer(), "o/b#2")
        assert_that(said, equal_to("it cannot be read"))

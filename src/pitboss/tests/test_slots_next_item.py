"""``slots next TICKET`` and the owner's priorities (pitboss#371).

The cause: the sweep ranked a PR ``NEXT 24`` and printed briefs only for the
first suggestions, so the orchestrator wrote a brief by hand and overrode the
order; and a ticket labelled p3 that the owner had stated as p0 was ranked by its
label.
"""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import configfile, ownerlabels
from . import fakes, quietworld, world
from .rankworld import publish
from .suggestions import next_output, parsed
from .says import says

PROJECT = world.PROJECT


class TestOneItem(unittest.TestCase):
    """The brief of one item is the suggestion's own text, headed by its place."""

    def test_the_usage_text_states_it(self) -> None:
        """The words of ``slots`` say what ``next`` does with one."""
        found = world.invoke(world.make_world(), "slots", "--help")
        says(found.out, "for 'next', one ticket or PR")

    def test_the_first_and_the_next_three_have_a_brief(self) -> None:
        """So a first with an issue is not the only item dispatched from a brief."""
        here = world.make_world()
        more = [dict(world.TICKET, number=number) for number in range(10, 18)]
        here.bodies[fakes.page(f"{PROJECT}/issues?state=open&labels=urgent")] = more
        found = parsed(next_output(here))
        assert_that([len(brief) > 1 for _, brief in found[:4]], equal_to([True] * 4))


Tickets = Mapping[int, tuple[str, str]]
OPEN: Tickets = {9: ("p3", "open"), 10: ("p1", "open"), 11: ("p2", "open")}
CLOSED_NINE: Tickets = {**OPEN, 9: ("p3", "closed")}


def priorities(
    ranks: Sequence[str], owner: Mapping[str, str], tickets: Tickets = OPEN
) -> world.World:
    """Make a world with these priority labels, owner priorities and tickets.

    Args:
        ranks: the ``priority_labels``.
        owner: each ticket reference and the owner's stated priority.
        tickets: each ticket's number, label and state; 9 is p3, 10 p1, 11 p2.

    Returns:
        The world.
    """
    here = world.make_world()
    names = str(list(ranks)).replace("'", '"')
    quietworld.edit_config(here, '["urgent"]', names)
    table = "".join(f'"{ticket}" = "{stated}"\n' for ticket, stated in owner.items())
    quietworld.edit_config(
        here, "[slots]", "[slots.owner_priorities]\n" + table + "[slots]"
    )
    publish(here, ranks, tickets)
    return here


NINTH = "owner/project#9"
SAID = f"LABEL DISAGREES: {NINTH} is labelled p3, the owner's stated priority is p0"
ALL = ["p0", "p1", "p2", "p3"]
SOME = ["p0", "p1"]
OWNER = {NINTH: "p0"}
TEN = "owner/project#10"
ELEVEN = "owner/project#11"


class TestOwnerPriorities(unittest.TestCase):
    """A ticket ranks by the owner's stated priority, and a differing label is said."""

    def test_a_stated_priority_that_cannot_be_read_is_refused(self) -> None:
        """A label the order has not, and a ticket that names no repository."""
        for ticket, stated in ((NINTH, "p7"), ("#9", "p0")):
            with self.subTest(ticket):
                here = priorities(SOME, {ticket: stated})
                with self.assertRaises(ValueError) as caught:
                    configfile.load(here.config, here.workspace)
                said = f"{ticket!r} = {stated!r}"
                assert_that(str(caught.exception), contains_string(said))

    def test_a_stated_priority_that_is_not_a_table_is_refused(self) -> None:
        """``owner_priorities = "p0"`` names no ticket."""
        with self.assertRaisesRegex(ValueError, "must be a table"):
            ownerlabels.parse({"owner_priorities": "p0"}, SOME)

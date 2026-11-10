"""``slots next TICKET`` and the owner's priorities (pitboss#371).

The cause: the sweep ranked a PR ``NEXT 24`` and printed briefs only for the
first suggestions, so the orchestrator wrote a brief by hand and overrode the
order; and a ticket labelled p3 that the owner had stated as p0 was ranked by its
label.
"""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import configfile, ownerlabels
from . import fakes, quietworld, test_flow_sweep, world
from .rankworld import publish
from .suggestions import next_output, parsed, third
from .test_commands import sweep
from .test_owner_repositories import lines_of

PROJECT = world.PROJECT


def offered(output: str) -> Sequence[str]:
    """The tickets an output lists to start, in order.

    Args:
        output: what ``slots next`` printed.

    Returns:
        Their references.
    """
    return re.findall(r"^NEXT \d+\. (\S+#\d+) \(start a PR", output, re.MULTILINE)


def printed(here: world.World, start: str) -> Sequence[Sequence[str]]:
    """The lines that start so, in what ``slots next`` and the sweep print.

    Args:
        here: the world.
        start: the first characters of the lines.

    Returns:
        The lines of ``slots next``, then those of the sweep.
    """
    outputs = (next_output(here), sweep(here).out)
    return [lines_of(each, start) for each in outputs]


def one(here: world.World, *references: str) -> world.Result:
    """Run ``slots next --config NAME REFERENCE`` at the fixed time.

    Args:
        here: the world.
        *references: the words after the configuration.

    Returns:
        What it did.
    """
    now = ("--now", world.FUTURE)
    return world.invoke(
        here, "slots", "next", "--config", here.config, *references, *now
    )


def after_first(output: str) -> Sequence[str]:
    """The lines of an output after its first, less the PITBOSS-SLOT marker.

    Args:
        output: what a command printed.

    Returns:
        The lines.
    """
    return [each for each in output.splitlines()[1:] if each[:13] != "PITBOSS-SLOT:"]


class TestOneItem(unittest.TestCase):
    """The brief of one item is the suggestion's own text, headed by its place."""

    def test_each_item_gets_the_text_of_its_suggestion(self) -> None:
        """The lines after the first are those of the suggestion; it says the place."""
        here = world.make_world()
        wanted = parsed(next_output(here))
        cases = [
            ("#1", "NEXT 2 of 4, first in the order: resolve the conflict"),
            ("project#3", "NEXT 3 of 4, out of order, 1 ahead of it: review the Plan"),
            ("owner/project#9", "NEXT 4 of 4, out of order, 2 ahead of it: start a PR"),
        ]
        for (spelling, first), suggestion in zip(cases, wanted):
            with self.subTest(spelling):
                found = one(here, spelling).out
                assert_that(found.splitlines()[0], contains_string(first))
                assert_that(list(after_first(found)), equal_to(list(suggestion[1])))

    def test_a_ruling_is_placed_before_the_list(self) -> None:
        """A PR at an Opus ruling has no NEXT line; the first line says so."""
        here = test_flow_sweep.world_with(test_flow_sweep.TWO_PLAN_REJECTIONS)
        found = one(here, "owner/project#3").out
        assert_that(found, contains_string("NEXT ruling, owed before every NEXT line"))
        assert_that(list(after_first(found)), equal_to(list(third(here)[1])))

    def test_a_reference_that_is_not_offered_is_refused(self) -> None:
        """Nothing on standard output, a status and a sentence on standard error."""
        here = world.make_world()
        cases = [
            (["owner/project#99"], 1, "UNKNOWN: owner/project#99 is not in the order"),
            (["banana"], 2, "takes a ticket as owner/repo#N"),
            (["#1", "#3"], 2, "takes one ticket or PR"),
        ]
        for words, code, said in cases:
            with self.subTest(words):
                found = one(here, *words)
                assert_that(
                    (found.code, found.out, said in found.err),
                    equal_to((code, "", True)),
                )

    def test_the_usage_text_states_it(self) -> None:
        """The words of ``slots`` say what ``next`` does with one."""
        found = world.invoke(world.make_world(), "slots", "--help")
        assert_that(found.out, contains_string("for 'next', one ticket or PR"))

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
BOTH = [[SAID], [SAID]]
ALL = ["p0", "p1", "p2", "p3"]
SOME = ["p0", "p1"]
OWNER = {NINTH: "p0"}
TEN = "owner/project#10"
ELEVEN = "owner/project#11"
CASES = [
    # the labels, the owner's priorities, the tickets, the offer in order, the lines
    (ALL, OWNER, OPEN, [NINTH, TEN, ELEVEN], [SAID]),
    (ALL, {}, OPEN, [TEN, ELEVEN, NINTH], []),
    (ALL, OWNER | {ELEVEN: "p2"}, OPEN, [NINTH, TEN, ELEVEN], [SAID]),
    (SOME, OWNER, OPEN, [NINTH, TEN], [SAID]),
    (SOME, {}, OPEN, [TEN], []),
    (SOME, OWNER, CLOSED_NINE, [TEN], []),
]


class TestOwnerPriorities(unittest.TestCase):
    """A ticket ranks by the owner's stated priority, and a differing label is said."""

    def test_the_order_and_the_lines(self) -> None:
        """Ranked as the owner says; a line only where the label differs."""
        for index, case in enumerate(CASES):
            ranks, owner, tickets, order, lines = case
            with self.subTest(index):
                output = next_output(priorities(ranks, owner, tickets))
                assert_that(offered(output), equal_to(order))
                assert_that(lines_of(output, "LABEL DIS"), equal_to(lines))

    def test_the_sweep_prints_the_line(self) -> None:
        """The sweep and ``slots next`` say the same."""
        here = priorities(ALL, OWNER)
        assert_that(printed(here, "LABEL DIS"), equal_to(BOTH))

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

    def test_a_ticket_an_open_pr_works_on_gets_the_line(self) -> None:
        """The line is for each ticket whose label differs, taken or not."""
        here = priorities(ALL, OWNER)
        title = "Fixes #9"
        here.bodies[f"{PROJECT}/pulls/2"] = fakes.pull_body(2, title=title)
        assert_that(offered(next_output(here)), equal_to([TEN, ELEVEN]))
        assert_that(printed(here, "LABEL DIS"), equal_to(BOTH))

    def test_a_stated_priority_nothing_can_use_is_said(self) -> None:
        """A repository that is not configured, and a ticket that cannot be read."""
        owner = {"elsewhere/repo#5": "p0", "owner/project#99": "p1", NINTH: "p0"}
        here = priorities(ALL, owner)
        lines = [
            "OWNER PRIORITY UNREAD: elsewhere/repo#5 = p0:"
            " its repository is not configured",
            "OWNER PRIORITY UNREAD: owner/project#99 = p1:"
            " the ticket cannot be read",
        ]
        assert_that(printed(here, "OWNER PRI"), equal_to([lines, lines]))
        assert_that(printed(here, "LABEL DIS"), equal_to(BOTH))

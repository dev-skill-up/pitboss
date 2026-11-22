"""Plan 6.5: one decision for one item, whichever command asks (keyword: one-path)."""

import re
import unittest
from typing import Callable, Sequence

from hamcrest import assert_that, equal_to

from . import sceneruns

NEXT_LINE = re.compile(r"^NEXT \d+ of \d+\. (.+?: ([^ :]+#\d+): .*)$")
TITLE = re.compile(r" \([^()]*\)$")
AT_LEAST = 3


def walk() -> Sequence[tuple[str, str]]:
    """Each decision ``slots next`` printed, with its item.

    Returns:
        The item and the decision part of each ``NEXT n of m.`` line, in order,
        without the title the line ends with.
    """
    out = sceneruns.command_line("slots", "next").out
    found = [NEXT_LINE.match(each) for each in out.splitlines()]
    return [(each[2], TITLE.sub("", each[1])) for each in found if each]


def first_line(*words: str) -> str:
    """The decision a command prints for an item.

    Args:
        *words: the command and its arguments.

    Returns:
        Its first line.
    """
    return sceneruns.command_line(*words).out.splitlines()[0]


def agreeing(same: Callable[[str, str], bool]) -> tuple[bool, Sequence[bool]]:
    """Whether a relation holds for each item of ``slots next``.

    Args:
        same: the relation, on an item and its ``NEXT`` line's decision.

    Returns:
        Whether at least 3 items were compared, and the answer for each.
    """
    decided = walk()
    return len(decided) >= AT_LEAST, [same(*each) for each in decided]


class TestOneDecision(unittest.TestCase):
    """Plan 6.5: the same decision for the same item, whichever command asks."""

    def test_6_5_next_and_slots_next_agree_on_every_item(self) -> None:
        """For each item of ``slots next``, both commands print one line."""
        many, same = agreeing(
            lambda item, _: first_line("next", item)
            == first_line("slots", "next", item)
        )
        assert_that((many, set(same)), equal_to((True, {True})))

    def test_6_5_next_prints_the_decision_part_of_each_next_line(self) -> None:
        """For each item, ``next <item>`` is the decision of its ``NEXT`` line."""
        many, same = agreeing(lambda item, said: first_line("next", item) == said)
        assert_that((many, set(same)), equal_to((True, {True})))

    def test_6_5_dispatch_next_acts_on_the_head_of_the_walk(self) -> None:
        """``act dispatch-next`` prints the first item, whose decision is ``next``'s."""
        item, said = walk()[0]
        printed = sceneruns.command_line("act", "dispatch-next", "owner/project")
        assert_that(
            (printed.out.strip(), first_line("next", item)), equal_to((item, said))
        )

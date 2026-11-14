"""A ticket marked as superseded is not offered to start (pitboss#388).

The cause: quire#573 was offered as "start a PR" after its work had moved to four
other tickets, which were not ranked with its p0 and its age of 2026-10-13.
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import supersedes
from . import rankworld, world
from .fastvariants import mark_superseded as listed
from .rankworld import mentioning, next_output, starts

NINTH = "owner/project#9"
ONLY = ["owner/project#1", "owner/project#3", "owner/project#10"]


class TestParse(unittest.TestCase):
    """The configuration and the comment line."""

    def test_the_configuration(self) -> None:
        """A list of tickets, or none."""
        assert_that(list(supersedes.parse({})), equal_to([]))
        assert_that(list(supersedes.parse({"superseded": [NINTH]})), equal_to([NINTH]))

    def test_what_is_refused(self) -> None:
        """A table, a bare number, a ticket of no repository, a number."""
        for value in ({"a": "b"}, ["#9"], ["owner/project"], [9], "owner/project#9"):
            with (
                self.subTest(value),
                self.assertRaisesRegex(ValueError, "must be a list"),
            ):
                supersedes.parse({"superseded": value})

    def test_the_comment_line(self) -> None:
        """A line that starts with the word marks the ticket; a sentence does not."""
        cases = {
            "Superseded.": True,
            "superseded: the work moved": True,
            "Status\n  SUPERSEDED by owner/lib#3 \nmore": True,
            "Superseded by #4": True,
            "the original plan is superseded by it": False,
            "Not superseded": False,
            "Supersededness": False,
            "Superseded, then restored": False,
            "Superseded by": True,
            "": False,
        }
        for text, expected in cases.items():
            with self.subTest(text):
                assert_that(supersedes.marked([text]), equal_to(expected))
        assert_that(supersedes.marked([]), equal_to(False))


def offered(text: str, *comments: Mapping[str, str]) -> bool:
    """Whether ticket 9, with a body and comments, is offered by ``slots next``.

    Args:
        text: the body of ticket 9.
        *comments: its comments.

    Returns:
        True when a ``NEXT`` line names it.
    """
    return NINTH in starts(rankworld.blocked_world(text, comments=list(comments)))


class TestSlotsNext(unittest.TestCase):
    """The offer of ``slots next``."""

    def test_the_configuration_marks_it(self) -> None:
        """No line for ticket 9 at all; the others are offered."""
        here = world.make_world()
        listed(here)
        both = [world.TICKET, rankworld.LATER]
        here.bodies[rankworld.LIST] = both
        output = next_output(here)
        assert_that(starts(here), equal_to(ONLY))
        assert_that(mentioning(output, NINTH), equal_to([]))

    def test_a_comment_line_marks_it(self) -> None:
        """A member's line ``Superseded by ...`` does, a stranger's does not."""
        member = rankworld.comment("Superseded by owner/lib#3")
        stranger = rankworld.comment("Superseded.", "NONE")
        found = [offered("A ticket", member), offered("A ticket", stranger)]
        assert_that(found, equal_to([False, True]))

    def test_the_body_does_not_mark_it(self) -> None:
        """Only a comment does."""
        assert_that(offered("Superseded."), equal_to(True))

"""A ticket marked as superseded is not offered to start (pitboss#388).

The cause: quire#573 was offered as "start a PR" after its work had moved to four
other tickets, which were not ranked with its p0 and its age of 2026-10-13.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import supersedes
from . import rankworld, quietworld, world
from .rankworld import (
    lines_are,
    lines_of,
    mentioning,
    next_output,
    printed,
    starts,
    sweep,
)
from .test_closing_comment import BLOCKED_BY_FOUR, FOUR, tracking_world

NINTH = "owner/project#9"
SAID = f"SUPERSEDED {NINTH}"
LABELS = 'priority_labels = ["urgent"]'
ONLY = ["owner/project#1", "owner/project#3", "owner/project#10"]


def listed(here: world.World) -> None:
    """Mark ticket 9 as superseded in the configuration of a world.

    Args:
        here: the world.
    """
    marked = LABELS + '\nsuperseded = ["owner/project#9"]'
    quietworld.edit_config(here, LABELS, marked)


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


class TestSlotsNext(unittest.TestCase):
    """The offer and the line of ``slots next``."""

    def test_the_configuration_marks_it(self) -> None:
        """SUPERSEDED, and no start line for ticket 9; the others are offered."""
        here = world.make_world()
        listed(here)
        both = [world.TICKET, rankworld.LATER]
        here.bodies[rankworld.LIST] = both
        output = next_output(here)
        lines_are(output, "SUPERSEDED", [SAID])
        assert_that(starts(here), equal_to(ONLY))
        started = mentioning(output, "owner/project#9 (start a PR")
        assert_that(started, equal_to([]))

    def test_a_comment_line_marks_it(self) -> None:
        """A member's line ``Superseded by ...`` does, a stranger's does not."""
        member = rankworld.comment("Superseded by owner/lib#3")
        stranger = rankworld.comment("Superseded.", "NONE")
        here = rankworld.blocked_world("A ticket", comments=[member])
        printed(here, "SUPERSEDED", [SAID])
        other = rankworld.blocked_world("A ticket", comments=[stranger])
        printed(other, "SUPERSEDED", [])

    def test_the_body_does_not_mark_it(self) -> None:
        """Only a comment does."""
        here = rankworld.blocked_world("Superseded.")
        printed(here, "SUPERSEDED", [])

    def test_the_tracking_ticket_and_its_four_blockers(self) -> None:
        """quire#573: SUPERSEDED, BLOCKED by four, each blocker ranked with it."""
        here = tracking_world()
        listed(here)
        output = next_output(here)
        lines_are(output, "SUPERSEDED", [SAID])
        lines_are(output, "BLOCKED", [BLOCKED_BY_FOUR])
        assert_that(
            starts(here),
            equal_to(["owner/project#1", "owner/project#3", *FOUR, "owner/project#10"]),
        )
        assert_that(len(lines_of(output, "BLOCKS")), equal_to(4))
        for each in FOUR:
            found = f"{each} (start a PR urgent, opened 2026-09-01,"
            assert_that(output, contains_string(found))

    def test_the_sweep_prints_the_same(self) -> None:
        """The sweep has the line once, and counts no start for the ticket."""
        here = tracking_world()
        listed(here)
        out = sweep(here).out
        lines_are(out, "SUPERSEDED", [SAID])
        lines_are(out, "BLOCKED", [BLOCKED_BY_FOUR])
        assert_that(out, contains_string("SLOTS FREE 1: 7 queued"))

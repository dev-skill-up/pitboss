"""Every brief starts with the line the watcher reads (keyword: slots-watch, #415)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to, starts_with

from .. import briefkind
from . import briefmake, watchworld, world
from .test_not_the_head import TEN, queued
from .transcripts import brief, call

Kind = briefkind.Kind
REFERENCE = "o/r#7"
FIRST = {
    Kind.NEW_PR: "start",
    Kind.FIRST_ROUND: "fix",
    Kind.FIX_REVIEW: "fix",
    Kind.FIX_CI: "fix",
    Kind.RESOLVE_CONFLICT: "fix",
    Kind.REVIEW_FULL: "review",
    Kind.REVIEW_PLAN: "review",
    Kind.REVIEW_FIX_ROUND: "review",
    Kind.RULING: "ruling",
}


class TestBriefLines(unittest.TestCase):
    """A brief names its item and kind in a line of its own; it has no marker."""

    def test_no_brief_has_a_marker_line_and_each_starts_at_its_goal(self) -> None:
        """The first line is the Goal, and the brief says no PITBOSS-SLOT."""
        for kind in FIRST:
            with self.subTest(kind.name):
                found = briefmake.text(kind)
                assert_that(found.splitlines()[0], starts_with("Goal: "))
                assert_that("PITBOSS-SLOT" in found, equal_to(False))

    def test_the_printed_brief_of_a_ticket_starts_at_its_goal(self) -> None:
        """``slots next TICKET`` prints the brief from its Goal, below the divider."""
        here = queued()
        shown = world.invoke(
            here, "slots", "next", TEN, "--config", here.config, "--now", world.FUTURE
        )
        lines = shown.out.splitlines()
        at = next(i for i, each in enumerate(lines) if each.startswith("--- brief 1:"))
        assert_that(lines[at + 1], starts_with("Goal: ticket "))


def read_as(text: str) -> tuple[Sequence[str], Sequence[str]]:
    """What the watcher holds and reads for a running agent with this brief.

    Args:
        text: the agent's brief.

    Returns:
        The agents held and the kinds read.
    """
    records = [brief("a1", text, watchworld.RECENT), call("Bash", watchworld.RECENT)]
    made = watchworld.play({"a1": records})
    return made.held, made.kinds


class TestWatcherReads(unittest.TestCase):
    """The watcher takes the ticket and the kind from the lines of the brief."""

    def test_a_pasted_brief_keeps_the_marker_even_after_other_lines(self) -> None:
        """A line before it (the NOT THE HEAD line) does not hide it."""
        pasted = "NOT THE HEAD: x\n" + briefmake.text(Kind.REVIEW_FULL)
        assert_that(read_as(pasted), equal_to((["a1"], ["review"])))

    def test_the_marker_wins_over_a_goal_line(self) -> None:
        """A brief with both: the marker's kind and ticket."""
        text = "PITBOSS-SLOT: o/r#7 fix\nGoal: ticket o/r#8: other\n"
        assert_that(read_as(text), equal_to((["a1"], ["fix"])))

    def test_each_kind_of_brief_is_read_as_its_kind(self) -> None:
        """A worker's start, a worker's fix, a review and a ruling, from their lines."""
        found = {kind: read_as(briefmake.text(kind))[1] for kind in FIRST}
        assert_that(found, equal_to({kind: [word] for kind, word in FIRST.items()}))

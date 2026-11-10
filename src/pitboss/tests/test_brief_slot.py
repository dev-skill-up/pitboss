"""Every brief starts with the line the watcher reads (keyword: slots-watch, #415)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

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


class TestFirstLine(unittest.TestCase):
    """The marker line of each kind of brief."""

    def test_each_kind_of_brief_starts_with_its_marker(self) -> None:
        """A worker's start, a worker's fix, a review and a ruling."""
        found = {
            kind: briefmake.text(kind).splitlines()[0].rpartition(" ")[2]
            for kind in FIRST
        }
        assert_that(found, equal_to(FIRST))

    def test_the_marker_names_the_reference_of_the_subject(self) -> None:
        """The reference the brief is about, in the line the watcher reads."""
        line = briefmake.text(Kind.NEW_PR).splitlines()[0]
        assert_that(line.startswith("PITBOSS-SLOT: "), equal_to(True))
        assert_that(line.split()[1], equal_to(briefmake.SUBJECT.reference))

    def test_the_printed_brief_of_a_ticket_has_it_before_the_goal(self) -> None:
        """``slots next TICKET`` prints the brief, marker first."""
        here = queued()
        shown = world.invoke(
            here, "slots", "next", TEN, "--config", here.config, "--now", world.FUTURE
        )
        lines = shown.out.splitlines()
        at = lines.index(f"PITBOSS-SLOT: {TEN} start")
        assert_that(lines[at + 1].startswith("Goal: ticket "), equal_to(True))


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
    """The watcher takes the ticket and the kind from the marker."""

    def test_a_pasted_brief_keeps_the_marker_even_after_other_lines(self) -> None:
        """A line before it (the NOT THE HEAD line) does not hide it."""
        pasted = "NOT THE HEAD: x\n" + briefmake.text(Kind.REVIEW_FULL)
        assert_that(read_as(pasted), equal_to((["a1"], ["review"])))

    def test_the_marker_wins_over_a_goal_line(self) -> None:
        """A brief with both: the marker's kind and ticket."""
        text = "PITBOSS-SLOT: o/r#7 fix\nGoal: ticket o/r#8: other\n"
        assert_that(read_as(text), equal_to((["a1"], ["fix"])))

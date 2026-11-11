"""The task list comes from the real state, a line per item (tasklist-state, #471)."""

import datetime
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import world
from .test_handback import slots, start

CLOSED = f"{world.PROJECT}/pulls?state=closed&sort=updated&direction=desc&per_page=30"
HOUR = datetime.timedelta(hours=1)
NOW = world.START
HEADER = "Task list, from the ledger and the open PRs (never kept by hand)"


def stamp(when: datetime.datetime) -> str:
    """A GitHub time.

    Args:
        when: the time.

    Returns:
        It, with a ``Z``.
    """
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def listed(here: world.World, mark: str = "") -> Sequence[str]:
    """The lines ``slots tasklist`` prints at the start time.

    Args:
        here: the world.
        mark: the mark the lines start with; every line when empty.

    Returns:
        The lines.
    """
    out = slots(here, "tasklist", "--now", NOW.isoformat()).out
    return [each for each in out.splitlines() if each.startswith(mark)]


class TestChecklist(unittest.TestCase):
    """The format of ``update_progress_checklist``, from the ledger and GitHub."""

    def test_the_header_and_a_blank_line_come_first(self) -> None:
        """The header, then a blank line, then one line for each item."""
        lines = listed(world.make_world())
        assert_that(lines[:2], equal_to([HEADER, ""]))

    def test_a_running_agent_is_a_line_with_its_slot(self) -> None:
        """A star, the agent named, and its slot."""
        here = world.make_world()
        start(here)
        running = listed(here, "✱")
        assert_that(len(running), equal_to(1))
        assert_that(running[0], contains_string("agent-1, slot tiny"))

    def test_a_queued_ticket_is_a_circle_with_its_next_step(self) -> None:
        """Nothing is grouped: one circle line for the ticket."""
        queued = listed(world.make_world(), "○")
        assert_that(queued[0], contains_string("; next: "))

    def test_a_merged_pr_is_a_check_mark_only_when_merged_lately(self) -> None:
        """Not merged, merged long ago, and merged in the last day."""
        here = world.make_world()
        here.bodies[CLOSED] = [
            {"number": 7, "merged_at": stamp(NOW - HOUR)},
            {"number": 8, "merged_at": None},
            {"number": 9, "merged_at": stamp(NOW - 30 * HOUR)},
        ]
        assert_that(listed(here, "✓"), equal_to(["✓ owner/project#7: merged"]))

    def test_a_list_github_cannot_give_has_no_merged_line(self) -> None:
        """A refused read and a text that is not JSON add no line."""
        for body in (None, "not json"):
            here = world.make_world()
            if body is not None:
                here.bodies[CLOSED] = body
            assert_that(listed(here, "✓"), equal_to([]))

    def test_the_list_follows_a_set_and_a_free(self) -> None:
        """It is replaced at the dispatch and again at the hand-back."""
        here = world.make_world()
        now = ("--now", NOW.isoformat())
        placed = slots(
            here, "set", "tiny", "agent-1", "#9", *now, "--running", "agent-1"
        )
        freed = slots(here, "free", "tiny", "--done", "agent-1", *now)
        assert_that(
            (HEADER in placed.out, HEADER in freed.out, "\u2731" in freed.out),
            equal_to((True, True, False)),
        )

"""Tests of the ``TASK LIST`` block and the one-ticket-per-line check (pitboss#344)."""

import re
import unittest
from typing import Sequence

from hamcrest import (
    assert_that,
    contains_string,
    equal_to,
    has_length,
    starts_with,
)

from .. import config, ledger, tasklist, work
from . import fakes, liveagents, test_work, world
from .test_handback import start
from .test_quiet import at

PROJECT = config.make_repo("owner", "project")
LOWER = f"{world.PROJECT}/issues?state=open&labels=low"
BATCHES: Sequence[tuple[str, Sequence[int]]] = (
    ("#194, #195, #196\nmerged #199\n#215, owner/repo#216, #218\n", [1, 3]),
    ("#1 is owner/project#1\n#2 again, #2", []),
)
FILES = (
    ("done: #194\nmerged: #195, #196\n", True),
    ("done: #194\nmerged: #195\n", False),
)


def sweep(here: world.World, *options: str) -> world.Result:
    """Sweep half an hour after the start.

    Args:
        here: the world.
        *options: more options.

    Returns:
        What it did.
    """
    live = liveagents.running(here)
    return world.invoke(here, "sweep", here.config, "--now", at(30), *live, *options)


def task_lines(here: world.World) -> Sequence[str]:
    """The ``TASK LIST`` lines of a sweep.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    return re.findall(r"^TASK LIST.*$", sweep(here).out, re.MULTILINE)


class TestBlock(unittest.TestCase):
    """The block is what is in flight, then what is next."""

    def test_header_says_what_the_list_is(self) -> None:
        """The first line says it is the task list and that filing adds nothing."""
        found = task_lines(world.make_world())
        assert_that(found[0], contains_string("the task list is exactly the lines"))
        assert_that(found[0], contains_string("filed or asked for is not added"))
        assert_that(found[0], contains_string('Next in sweep order: ...") is not'))
        assert_that(found[0], contains_string("no placeholder entry exists"))

    def test_next_lines_follow_the_next_order(self) -> None:
        """Each item of the NEXT order is a line, numbered as ``slots next`` does."""
        here = world.make_world()
        found = task_lines(here)
        args = ("slots", "next", here.config, "--now", at(30))
        shown = world.invoke(here, *args, *liveagents.running(here)).out
        wanted = re.findall(r"^NEXT (\d+)\. (\S+) ", shown, re.MULTILINE)[1:]
        assert_that(wanted, has_length(3))
        for (number, reference), line in zip(wanted, found[2:]):
            prefix = f"TASK LIST next {number}. {reference}:"
            assert_that(line, starts_with(prefix))

    def test_in_flight_comes_first_and_is_not_next(self) -> None:
        """A ticket in a slot is a line of its own, and not also a next line."""
        here = world.make_world()
        start(here)
        found = task_lines(here)
        flying = "TASK LIST in flight owner/project#9: slot tiny (agent-1)"
        assert_that(found[1], equal_to(flying))
        assert_that(sum("#9" in line for line in found), equal_to(1))
        assert_that(tasklist.crowded("\n".join(found[1:]), PROJECT), equal_to({}))

    def test_a_ticket_outside_the_order_is_not_in_it(self) -> None:
        """A ticket under a priority label the order does not offer is no line."""
        here = world.make_world()
        here.bodies[fakes.page(LOWER)] = [dict(world.TICKET, number=77)]
        shown = sweep(here).out
        assert_that(shown, contains_string("TASK LIST next 4. owner/project#9"))
        assert_that("#77" in shown, equal_to(False))

    def test_ready_drafts_are_numbered_after_the_running_line(self) -> None:
        """A draft to mark ready follows the running line; the items follow it."""
        queued = [test_work.item("owner/project#5", work.Category.NEW_PR)]
        book = ledger.Ledger(slots=(), failed={})
        ready = ["owner/project#4 (mark the PR ready)"]
        assert_that(
            tasklist.block(book, ready, queued)[3:],
            equal_to(
                [
                    "TASK LIST next 2. owner/project#4 (mark the PR ready)",
                    "TASK LIST next 3. owner/project#5: t",
                ]
            ),
        )


class TestOneTicketPerLine(unittest.TestCase):
    """A task-list line names one ticket."""

    def test_batches_are_refused(self) -> None:
        """A merged batch and a queue line name several tickets."""
        for text, lines in BATCHES:
            assert_that(sorted(tasklist.crowded(text, PROJECT)), equal_to(lines))

    def test_sweep_checks_a_file(self) -> None:
        """``sweep --task-list`` refuses a crowded line; ``refused`` says so."""
        for text, crowded in FILES:
            here = world.make_world()
            path = here.workspace / "tasks.txt"
            path.write_text(text)
            result = sweep(here, "--task-list", str(path))
            assert_that(("line 2: names 2" in result.out), equal_to(crowded))
            assert_that(tasklist.refused(str(path), PROJECT), equal_to(crowded))

    def test_the_refusal_says_one_line_per_ticket_and_no_more(self) -> None:
        """The text asks for one line per ticket and names no merged or queue ones."""
        found = tasklist.refusals("#1, #2\n", PROJECT)
        assert_that(
            found,
            equal_to(
                [
                    "TASK LIST REFUSED line 1: names 2 tickets"
                    " (owner/project#1, owner/project#2);"
                    " one task-list line per ticket"
                ]
            ),
        )

    def test_sweep_unreadable_file(self) -> None:
        """A file that is not there is said, not a traceback."""
        out = sweep(world.make_world(), "--task-list", "/none/tasks.txt").out
        assert_that(out, contains_string("TASK LIST REFUSED: cannot read"))


OPEN_REFS = ["owner/project#1", "owner/project#2", "owner/project#3", "owner/lib#4"]


class TestLive(unittest.TestCase):
    """The block from live state: open PRs with their CI, and the free slot."""

    def test_an_empty_ledger_says_the_slot_is_free_and_a_held_one_does_not(
        self,
    ) -> None:
        """``NO AGENT RUNNING`` only when no row holds an agent."""
        empty = world.make_world()
        held = world.make_world()
        start(held)
        said = [
            sweep(each).out.count("NO AGENT RUNNING: the slot is free")
            for each in (empty, held)
        ]
        assert_that(said, equal_to([1, 0]))

    def test_each_open_pr_has_a_line_with_its_ci_and_agent(self) -> None:
        """One line for each open PR; the agent that owns it, else none."""
        out = sweep(world.make_world()).out
        found = re.findall(r"^TASK LIST open (\S+): (.*)$", out, re.MULTILINE)
        assert_that(
            dict(found),
            equal_to({each: "CI green; agent none" for each in OPEN_REFS}),
        )

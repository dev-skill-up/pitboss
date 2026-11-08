"""Tests of the ``TASK LIST`` block and the one-ticket-per-line check (pitboss#344)."""

import re
import unittest
from typing import Sequence

from hamcrest import (
    assert_that,
    contains_string,
    equal_to,
    has_length,
    is_not,
    starts_with,
)

from .. import config, ledger, tasklist, work
from . import fakes, world
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
    return world.invoke(here, "sweep", here.config, "--now", at(30), *options)


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

    def test_next_lines_follow_the_next_order(self) -> None:
        """Each item of the NEXT order is a line, numbered as ``slots next`` does."""
        here = world.make_world()
        found = task_lines(here)
        shown = world.invoke(here, "slots", "next", here.config, "--now", at(30)).out
        wanted = re.findall(r"^NEXT (\d+)\. (\S+) ", shown, re.MULTILINE)
        assert_that(wanted, has_length(3))
        for (number, reference), line in zip(wanted, found[1:]):
            prefix = f"TASK LIST next {number}. {reference}:"
            assert_that(line, starts_with(prefix))

    def test_in_flight_comes_first_and_is_not_next(self) -> None:
        """A ticket in a slot is a line of its own, and not also a next line."""
        here = world.make_world()
        start(here)
        found = task_lines(here)
        assert_that(
            found[1],
            equal_to("TASK LIST in flight owner/project#9: slot tiny (agent-1)"),
        )
        assert_that([line for line in found if "#9" in line], has_length(1))

    def test_one_ticket_for_each_line(self) -> None:
        """No line of the block names several tickets."""
        here = world.make_world()
        start(here)
        found = task_lines(here)[1:]
        assert_that(tasklist.crowded("\n".join(found), PROJECT), equal_to({}))

    def test_a_ticket_outside_the_order_is_not_in_it(self) -> None:
        """A ticket under a priority label the order does not offer is no line."""
        here = world.make_world()
        here.bodies[fakes.page(LOWER)] = [dict(world.TICKET, number=77)]
        shown = sweep(here).out
        assert_that(shown, contains_string("TASK LIST next 3. owner/project#9"))
        assert_that(shown, is_not(contains_string("#77")))

    def test_ready_drafts_come_first_in_the_numbers(self) -> None:
        """A draft to mark ready is numbered first, and the items after it."""
        item = work.Item(
            category=work.Category.NEW_PR,
            reference="owner/project#5",
            created_at="2030-01-01T00:00:00Z",
            title="Five",
        )
        book = ledger.Ledger(slots=(), failed={})
        found = tasklist.block(book, ["owner/project#4 (mark the PR ready)"], [item])
        assert_that(
            found[1:],
            equal_to(
                [
                    "TASK LIST next 1. owner/project#4 (mark the PR ready)",
                    "TASK LIST next 2. owner/project#5: Five",
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

    def test_sweep_unreadable_file(self) -> None:
        """A file that is not there is said, not a traceback."""
        out = sweep(world.make_world(), "--task-list", "/none/tasks.txt").out
        assert_that(out, contains_string("TASK LIST REFUSED: cannot read"))

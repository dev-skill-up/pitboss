"""Tests of ``TASK LIST``, ``slots refreshed`` and the one-ticket-per-line check."""

import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import config, tasklist, tasklistrule
from . import world
from .test_evidence_rules import read, words
from .test_handback import slots, start
from .test_quiet import at

MERGED = f"{world.PROJECT}/{tasklist.MERGED_PATH}"
PROJECT = config.make_repo("owner", "project")
PULLS = [
    {"number": 3, "merged_at": "2030-01-01T00:10:00Z", "body": "Fixes #9\n"},
    {"number": 4, "merged_at": "2029-12-31T00:00:00Z", "body": "Fixes #8\n"},
    {"number": 5, "merged_at": None, "body": "Fixes #7\n"},
    {"number": 6, "merged_at": "2030-01-01T00:20:00Z", "body": "Fixes #1\nCloses #2\n"},
]
DONE = {"free": ("--done", "agent-1"), "heard": ()}
BATCHES: Sequence[tuple[str, Sequence[int]]] = (
    ("#194, #195, #196\nmerged #199\n#215, owner/repo#216, #218\n", [1, 3]),
    ("#1 is owner/project#1\n#2 again, #2", []),
)
FILES = (
    ("done: #194\nmerged: #195, #196\n", True),
    ("done: #194\nmerged: #195\n", False),
)


def merged_world() -> world.World:
    """A world whose project merged four PRs, one of them before the start.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies[MERGED] = PULLS
    return here


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


def handed_back(how: str) -> world.World:
    """A world whose agent handed back by ``free`` or ``heard``.

    Args:
        how: the action.

    Returns:
        The world.
    """
    here = world.make_world()
    start(here)
    slots(here, how, "tiny", *DONE[how], "--now", at(1))
    return here


def refreshed_world(here: world.World, minute: int) -> world.World:
    """The world after ``slots refreshed``.

    Args:
        here: the world.
        minute: minutes after the start.

    Returns:
        The same world.
    """
    slots(here, "refreshed", "--now", at(minute))
    return here


class TestMerged(unittest.TestCase):
    """The sweep names the tickets merged since the last refresh."""

    def test_merged_ticket_is_named(self) -> None:
        """A merged PR's ticket is a line; an unmerged PR's is not."""
        found = "\n".join(task_lines(merged_world()))
        assert_that(found, contains_string("TASK LIST owner/project#9: show it done"))
        assert_that(found, contains_string("PR 3 merged 2030-01-01T00:10:00Z; then"))
        assert_that("owner/project#7" in found, equal_to(False))

    def test_one_line_for_each_ticket(self) -> None:
        """A PR that fixes two tickets gives two lines, one ticket each."""
        found = task_lines(merged_world())
        assert_that([line for line in found if "PR 6" in line], has_length(2))
        assert_that(tasklist.crowded("\n".join(found), PROJECT), equal_to({}))

    def test_refreshed_hides_what_was_merged_before(self) -> None:
        """After ``slots refreshed``, only a later merge is named."""
        found = "\n".join(task_lines(refreshed_world(merged_world(), 15)))
        assert_that("owner/project#9" in found, equal_to(False))
        assert_that(found, contains_string("owner/project#1:"))

    def test_unreadable_repository(self) -> None:
        """A repository whose merged PRs cannot be read has a line of its own."""
        found = "\n".join(task_lines(world.make_world()))
        assert_that(found, contains_string("TASK LIST owner/project: its merged"))


class TestHandBack(unittest.TestCase):
    """The sweep names the ticket of an agent that handed back."""

    def test_free_and_heard(self) -> None:
        """A freed slot's ticket is named, and a notifying agent's."""
        for how in DONE:
            found = task_lines(handed_back(how))
            assert_that(found[0], contains_string("TASK LIST owner/project#9: an"))

    def test_a_ticket_is_noted_once(self) -> None:
        """Two notices from one agent give one line."""
        here = handed_back("heard")
        slots(here, "heard", "tiny", "--now", at(2))
        found = [line for line in task_lines(here) if "#9" in line]
        assert_that(found, has_length(1))

    def test_refreshed_forgets_the_hand_backs(self) -> None:
        """``slots refreshed`` clears them."""
        found = "\n".join(task_lines(refreshed_world(handed_back("free"), 2)))
        assert_that("an agent handed back" in found, equal_to(False))


class TestOneTicketPerLine(unittest.TestCase):
    """A task-list line names one ticket."""

    def test_batches_are_refused(self) -> None:
        """A merged batch and a queue line name several tickets."""
        for text, lines in BATCHES:
            assert_that(sorted(tasklist.crowded(text, PROJECT)), equal_to(lines))

    def test_sweep_checks_a_file(self) -> None:
        """``sweep --task-list`` refuses a crowded line; ``refused`` says so."""
        for text, crowded in FILES:
            here = merged_world()
            path = here.workspace / "tasks.txt"
            path.write_text(text)
            result = sweep(here, "--task-list", str(path))
            assert_that(("line 2: names 2" in result.out), equal_to(crowded))
            assert_that(tasklist.refused(str(path), PROJECT), equal_to(crowded))

    def test_sweep_unreadable_file(self) -> None:
        """A file that is not there is said, not a traceback."""
        out = sweep(world.make_world(), "--task-list", "/none/tasks.txt").out
        assert_that(out, contains_string("TASK LIST REFUSED: cannot read"))


class TestRule(unittest.TestCase):
    """The sentence is in the rules and once in the brief text the sweep prints."""

    def test_rules_hold_the_sentence(self) -> None:
        """rules.md says it, with one line per ticket."""
        rule = tasklistrule.TASK_LIST_RULE
        assert_that(words(read("rules.md")), contains_string(rule))
        assert_that(rule, contains_string("one task-list line per ticket"))
        assert_that(rule, contains_string("merged ones included, queue ones included"))
        assert_that(tasklist.crowded(rule, PROJECT), equal_to({}))

    def test_sweep_prints_it_once(self) -> None:
        """The sweep's reminders hold the sentence once."""
        out = sweep(world.make_world()).out
        assert_that(out.count(tasklistrule.TASK_LIST_RULE), equal_to(1))

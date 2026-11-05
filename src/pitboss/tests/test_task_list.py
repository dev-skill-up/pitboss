"""Tests of ``TASK LIST``, ``slots refreshed`` and the one-ticket-per-line check."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length, is_not

from .. import config, tasklist
from . import world
from .test_evidence_rules import read, words
from .test_handback import slots, start
from .test_quiet import at

START = world.START
MERGED = f"{world.PROJECT}/{tasklist.MERGED_PATH}"
PROJECT = config.make_repo("owner", "project")
PULLS = [
    {"number": 3, "merged_at": "2030-01-01T00:10:00Z", "body": "Fixes #9\n"},
    {"number": 4, "merged_at": "2029-12-31T00:00:00Z", "body": "Fixes #8\n"},
    {"number": 5, "merged_at": None, "body": "Fixes #7\n"},
    {"number": 6, "merged_at": "2030-01-01T00:20:00Z", "body": "Fixes #1\nCloses #2\n"},
]


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


def task_lines(out: str) -> Sequence[str]:
    """The ``TASK LIST`` lines of a sweep.

    Args:
        out: its output.

    Returns:
        The lines.
    """
    return [line for line in out.splitlines() if line.startswith("TASK LIST")]


class TestMerged(unittest.TestCase):
    """The sweep names the tickets merged since the last refresh."""

    def test_merged_ticket_is_named(self) -> None:
        """A merged PR's ticket is a line; an unmerged PR's is not."""
        found = "\n".join(task_lines(sweep(merged_world()).out))
        assert_that(
            found,
            contains_string(
                "TASK LIST owner/project#9: show it done: PR 3 merged"
                " 2030-01-01T00:10:00Z; then run 'pitboss slots refreshed"
            ),
        )
        assert_that(found, contains_string("owner/project#8"))
        assert_that(found, is_not(contains_string("owner/project#7")))

    def test_one_line_for_each_ticket(self) -> None:
        """A PR that fixes two tickets gives two lines, one ticket each."""
        found = task_lines(sweep(merged_world()).out)
        mine = [line for line in found if "PR 6" in line]
        assert_that(mine, has_length(2))
        assert_that(tasklist.crowded("\n".join(found), PROJECT), equal_to({}))

    def test_refreshed_hides_what_was_merged_before(self) -> None:
        """After ``slots refreshed``, only a later merge is named."""
        here = merged_world()
        refreshed = slots(here, "refreshed", "--now", "2030-01-01T00:15:00+00:00")
        assert_that(refreshed.code, equal_to(0))
        found = "\n".join(task_lines(sweep(here).out))
        assert_that(found, is_not(contains_string("owner/project#9")))
        assert_that(found, is_not(contains_string("owner/project#8")))
        assert_that(found, contains_string("owner/project#1:"))

    def test_unreadable_repository(self) -> None:
        """A repository whose merged PRs cannot be read has a line of its own."""
        here = merged_world()
        del here.bodies[MERGED]
        found = "\n".join(task_lines(sweep(here).out))
        assert_that(
            found, contains_string("TASK LIST owner/project: its merged pull requests")
        )


class TestHandBack(unittest.TestCase):
    """The sweep names the ticket of an agent that handed back."""

    def handed_back(self, how: str) -> world.World:
        """A world whose agent handed back by ``free`` or ``heard``.

        Args:
            how: ``free`` or ``heard``.

        Returns:
            The world.
        """
        here = world.make_world()
        start(here)
        if how == "free":
            slots(here, "free", "tiny", "--done", "agent-1", "--now", at(1))
        else:
            slots(here, "heard", "tiny", "--now", at(1))
        return here

    def test_free(self) -> None:
        """A freed slot's ticket is named."""
        found = task_lines(sweep(self.handed_back("free")).out)
        assert_that(found[0], contains_string("TASK LIST owner/project#9: an agent"))

    def test_heard(self) -> None:
        """A slot whose agent notified is named too."""
        found = task_lines(sweep(self.handed_back("heard")).out)
        assert_that(found[0], contains_string("TASK LIST owner/project#9: an agent"))

    def test_refreshed_forgets_the_hand_backs(self) -> None:
        """``slots refreshed`` clears them."""
        here = self.handed_back("free")
        slots(here, "refreshed", "--now", at(2))
        found = "\n".join(task_lines(sweep(here).out))
        assert_that(found, is_not(contains_string("an agent handed back")))


class TestOneTicketPerLine(unittest.TestCase):
    """A task-list line names one ticket."""

    def test_batches_are_refused(self) -> None:
        """A merged batch and a queue line name several tickets."""
        text = "#194, #195, #196\nmerged #199\n#215, owner/repo#216, #218\n"
        assert_that(
            sorted(tasklist.crowded(text, PROJECT)),
            equal_to([1, 3]),
        )

    def test_same_ticket_spelled_twice(self) -> None:
        """``#1`` and ``owner/project#1`` are one ticket."""
        assert_that(tasklist.crowded("#1 is owner/project#1", PROJECT), equal_to({}))

    def test_sweep_refuses_a_file(self) -> None:
        """``sweep --task-list`` prints the refusal and exits 1."""
        here = merged_world()
        path = here.workspace / "tasks.txt"
        path.write_text("done: #194\nmerged: #195, #196\n")
        result = sweep(here, "--task-list", str(path))
        assert_that(result.out, contains_string("TASK LIST REFUSED line 2: names 2"))
        assert_that(result.code, equal_to(1))

    def test_sweep_accepts_a_file(self) -> None:
        """A list with one ticket on each line is not refused."""
        here = merged_world()
        path = here.workspace / "tasks.txt"
        path.write_text("done: #194\nmerged: #195\n")
        assert_that(
            sweep(here, "--task-list", str(path)).out,
            is_not(contains_string("REFUSED")),
        )

    def test_sweep_unreadable_file(self) -> None:
        """A file that is not there is said, not a traceback."""
        here = merged_world()
        result = sweep(here, "--task-list", str(here.workspace / "none.txt"))
        assert_that(result.out, contains_string("TASK LIST REFUSED: cannot read"))


class TestRule(unittest.TestCase):
    """The sentence is in the rules and once in the brief text the sweep prints."""

    def test_rules_hold_the_sentence(self) -> None:
        """rules.md says it, with one line per ticket."""
        assert_that(words(read("rules.md")), contains_string(config.TASK_LIST_RULE))
        assert_that(config.TASK_LIST_RULE, contains_string("one task-list line per"))

    def test_sweep_prints_it_once(self) -> None:
        """The sweep's reminders hold the sentence once."""
        out = sweep(world.make_world()).out
        assert_that(out.count(config.TASK_LIST_RULE), equal_to(1))

    def test_text_lets_no_line_name_several_tickets(self) -> None:
        """The sentence names no ticket, and says merged and queued lines too."""
        assert_that(tasklist.crowded(config.TASK_LIST_RULE, PROJECT), equal_to({}))
        assert_that(
            config.TASK_LIST_RULE,
            contains_string("merged ones included, queue ones included"),
        )

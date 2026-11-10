"""``slots watch`` keeps the ledger from the agents' transcripts (pitboss#415)."""

import json
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import quietworld, transcripts, world
from .test_handback import slots
from .test_owner_repositories import lines_of
from .transcripts import brief, call, ended, result, write

NOW = "2030-01-01T00:00:00+00:00"
RECENT = "2029-12-31T23:59:00Z"
LONG_AGO = "2029-12-31T20:00:00Z"
GOAL = "WORKER: x\nGoal: ticket owner/project#{n}: A ticket\nTask: do it\n"
REVIEW_GOAL = "Goal: review owner/project#3\n"
MARKED = "PITBOSS-SLOT: owner/project#9 fix\nthe rest mentions SubagentHandback\n"


def watched(extra: str = "") -> tuple[world.World, pathlib.Path]:
    """A world whose configuration names a tasks directory.

    Args:
        extra: more keys of ``[slots]``.

    Returns:
        The world and the directory.
    """
    here = world.make_world()
    directory = here.workspace / "tasks"
    quietworld.edit_config(
        here, "[slots]", f'[slots]\nagents-dir = "{directory}"\n{extra}'
    )
    return here, directory


def watch(here: world.World, rounds: str = "1", seconds: str = "0") -> world.Result:
    """Run ``slots watch`` for some rounds at the fixed time.

    Args:
        here: the world.
        rounds: how many.
        seconds: the interval between them.

    Returns:
        What it did.
    """
    words = ("watch", "--rounds", rounds, "--interval", seconds, "--now", NOW)
    return slots(here, *words)


def held(here: world.World) -> Sequence[str]:
    """The agents the ledger file holds.

    Args:
        here: the world.

    Returns:
        Their names, for each row that has one.
    """
    rows = json.loads(here.ledger.read_text())["slots"]
    return [row["agent"] for row in rows if row["agent"]]


def running(directory: pathlib.Path, agent: str, number: int = 9) -> None:
    """Plant a running worker.

    Args:
        directory: the tasks directory.
        agent: its id.
        number: its ticket's number.
    """
    write(directory, agent, [brief(agent, GOAL.format(n=number), RECENT), call("Bash", RECENT)])


def handed_back(directory: pathlib.Path, agent: str) -> None:
    """Plant a worker that handed back.

    Args:
        directory: the tasks directory.
        agent: its id.
    """
    write(directory, agent, [
        brief(agent, GOAL.format(n=9), LONG_AGO),
        call("SubagentHandback", LONG_AGO),
        result(LONG_AGO, transcripts.HANDBACK_RESULT, ends=True),
    ])


class TestWatch(unittest.TestCase):
    """What a round writes and prints."""

    def test_a_new_running_agent_becomes_a_row_and_a_slot_is_free(self) -> None:
        """The ticket is the brief's Goal line; one of two slots is free."""
        here, directory = watched()
        running(directory, "a1")
        out = watch(here).out
        assert_that(held(here), equal_to(["a1"]))
        lines = out.splitlines()
        assert_that(lines[0], equal_to(
            "LEDGER CHANGED: slot tiny takes a1 on owner/project#9"))
        free = lines_of(out, "SLOT FREE")
        assert_that(len(free), equal_to(1))
        assert_that(free[0], contains_string(
            "1 of 2 free since 2030-01-01 00:00Z; first startable: owner/project#1"
            f" (pitboss slots next owner/project#1 --config {here.config})"))

    def test_a_full_cap_prints_no_free_slot_and_an_extra_agent_is_overcap(self) -> None:
        """Two agents fill two slots; a third has no slot."""
        here, directory = watched()
        for number, agent in enumerate(("a1", "a2", "a3"), start=7):
            running(directory, agent, number)
        out = watch(here).out
        assert_that(held(here), equal_to(["a1", "a2"]))
        assert_that(lines_of(out, "OVERCAP"), equal_to(["OVERCAP a3 owner/project#9"]))
        assert_that(lines_of(out, "SLOT FREE"), equal_to([]))

    def test_a_handback_frees_the_row(self) -> None:
        """The ledger row of an agent whose transcript ends in a hand-back is freed."""
        here, directory = watched()
        slots(here, "set", "tiny", "a1", "#9", "--running", "a1")
        handed_back(directory, "a1")
        out = watch(here).out
        assert_that(held(here), equal_to([]))
        assert_that(lines_of(out, "LEDGER CHANGED"), equal_to([
            "LEDGER CHANGED: slot tiny freed from a1 (owner/project#9): it handed back"]))
        assert_that(len(lines_of(out, "SLOT FREE")), equal_to(1))

    def test_a_reviewer_that_ended_its_turn_is_freed(self) -> None:
        """No hand-back tool: an assistant message that ends the turn."""
        here, directory = watched()
        slots(here, "set", "tiny", "a1", "#3", "--kind", "review", "--running", "a1")
        write(directory, "a1", [brief("a1", REVIEW_GOAL, LONG_AGO), ended(LONG_AGO)])
        watch(here)
        assert_that(held(here), equal_to([]))

    def test_an_agent_resumed_after_a_handback_runs_again(self) -> None:
        """Records after the hand-back result mean it works again."""
        here, directory = watched()
        slots(here, "set", "tiny", "a1", "#9", "--running", "a1")
        handed_back(directory, "a1")
        path = directory / "a1.output"
        path.write_text(path.read_text() + json.dumps(brief("a1", "go on", RECENT)) + "\n")
        watch(here)
        assert_that(held(here), equal_to(["a1"]))

    def test_the_word_in_a_brief_is_not_a_handback(self) -> None:
        """The marker line sets the ticket and kind; the prose is not a finish."""
        here, directory = watched()
        write(directory, "a1", [brief("a1", MARKED, RECENT), call("Bash", RECENT)])
        out = watch(here).out
        assert_that(held(here), equal_to(["a1"]))
        assert_that(lines_of(out, "LEDGER CHANGED"), equal_to([
            "LEDGER CHANGED: slot tiny takes a1 on owner/project#9"]))
        rows = json.loads(here.ledger.read_text())["slots"]
        assert_that(rows[0]["kind"], equal_to("fix"))

    def test_a_silent_agent_is_uncertain_and_keeps_its_row(self) -> None:
        """No new line for the idle minutes and no hand-back: said, never freed."""
        here, directory = watched()
        slots(here, "set", "tiny", "a1", "#9", "--running", "a1")
        write(directory, "a1", [brief("a1", GOAL.format(n=9), LONG_AGO), call("Bash", LONG_AGO)])
        write(directory, "a2", [brief("a2", GOAL.format(n=8), LONG_AGO), call("Bash", LONG_AGO)])
        out = watch(here).out
        assert_that(held(here), equal_to(["a1"]))
        assert_that(len(lines_of(out, "UNCERTAIN")), equal_to(1))
        assert_that(lines_of(out, "UNCERTAIN")[0], contains_string("a1 (owner/project#9)"))

    def test_other_files_are_not_agents(self) -> None:
        """A task output that is not a transcript is skipped."""
        here, directory = watched()
        directory.mkdir()
        (directory / "b1.output").write_text("plain output\n")
        (directory / "b2.output").write_text("{}\n")
        watch(here)
        assert_that(held(here), equal_to([]))

    def test_the_free_slot_line_repeats_every_round(self) -> None:
        """Until an agent fills the slot."""
        here, directory = watched()
        running(directory, "a1")
        assert_that(len(lines_of(watch(here, "3").out, "SLOT FREE")), equal_to(3))

    def test_without_a_directory_it_refuses(self) -> None:
        """The configuration names none."""
        found = watch(world.make_world())
        assert_that(found.code, equal_to(2))
        assert_that(found.err, contains_string("needs [slots] agents-dir"))

    def test_a_ticket_less_brief_still_takes_a_row(self) -> None:
        """No reference in the brief: the row names no ticket."""
        here, directory = watched()
        write(directory, "a1", [brief("a1", "do something", RECENT), call("Bash", RECENT)])
        out = watch(here).out
        assert_that(lines_of(out, "LEDGER CHANGED"), equal_to([
            "LEDGER CHANGED: slot tiny takes a1 on no ticket"]))

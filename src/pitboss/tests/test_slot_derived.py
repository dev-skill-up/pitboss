"""The held slots come from the running agents, not the ledger (pitboss#94)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, starts_with

from .. import slotheld
from . import fakes, suggestions, test_flow_sweep as flows, world
from .test_owner_repositories import lines_of
from .test_slot_commands import run_all


def calm() -> world.World:
    """The default world with PR 1 clean, so that no PR holds a slot.

    Returns:
        The world.
    """
    here = world.make_world()
    branch = {"sha": "1" * 40, "ref": "branch-1"}
    here.bodies[f"{world.PROJECT}/pulls/1"] = fakes.pull_body(1, head=branch)
    return here


def ran(here: world.World, command: Sequence[str], *running: str) -> str:
    """What a command printed, given the agents the session runs.

    Args:
        here: the world.
        command: the command's words before the configuration.
        *running: the names of the live agents.

    Returns:
        Its output.
    """
    return world.invoke(here, *command, here.config, "--running", *running).out


def said(output: str, start: str, wanted: int | Sequence[str]) -> None:
    """Assert the lines that start with some words, or how many there are.

    Args:
        output: what a command printed.
        start: the words.
        wanted: the lines, or their number.
    """
    found = lines_of(output, start)
    assert_that(len(found) if isinstance(wanted, int) else found, equal_to(wanted))


def plain(here: world.World, *command: str) -> str:
    """What a command printed, with no ``--running`` given.

    Args:
        here: the world.
        *command: the command's words before the configuration.

    Returns:
        Its output.
    """
    return world.invoke(here, *command, here.config).out


def stale_world() -> world.World:
    """A calm world whose ledger holds agent-1, which has finished.

    Returns:
        The world.
    """
    here = calm()
    run_all(here, [("set", "tiny", "agent-1", "#9", "--running", "agent-1")])
    return here


class TestTheSlotsAreDerived(unittest.TestCase):
    """The held slots come from the running agents, not the ledger (pitboss#94)."""

    def test_a_finished_agent_does_not_fill_its_slot(self) -> None:
        """Nothing runs: both slots are empty, as the live agents say."""
        said(ran(stale_world(), ("slots", "next")), "EMPTY SLOT", 2)

    def test_a_running_agent_the_ledger_lacks_holds_a_slot(self) -> None:
        """agent-2 runs, agent-1 is gone: agent-2 is unrecorded and nothing starts."""
        shown = ran(stale_world(), ("slots", "next"), "agent-2")
        said(shown, "UNRECORDED AGENT", 1)
        said(shown, "EMPTY SLOT", 0)

    def test_show_does_not_list_the_finished_agent_as_holding_its_slot(self) -> None:
        """``slots show`` derives the rows: no row names agent-1."""
        shown = ran(stale_world(), ("slots", "show"), "agent-2")
        assert_that("agent-1" in shown, equal_to(False))
        said(shown, "UNRECORDED AGENT", 1)
        assert_that(shown, contains_string("empty, but held by work"))

    def test_the_sweep_derives_them_too(self) -> None:
        """The sweep's ledger rows and its task list agree with ``slots show``."""
        shown = ran(stale_world(), ("sweep",), "agent-2")
        said(shown, "UNRECORDED AGENT", 1)
        assert_that("TASK LIST in flight" in shown, equal_to(False))

    def test_a_running_recorded_agent_keeps_its_slot(self) -> None:
        """The ledger's agent that runs is held, as it was."""
        shown = ran(stale_world(), ("slots", "show"), "agent-1")
        assert_that(shown, contains_string("slot tiny (small): owner/project#9"))
        said(shown, "UNRECORDED AGENT", 0)

    def test_no_running_option_computes_no_occupancy(self) -> None:
        """The agents are not known: no row, no held slot, the one line instead."""
        for command in (("slots", "show"), ("sweep",), ("slots", "next")):
            shown = plain(stale_world(), *command)
            said(shown, "slots: not computed", [slotheld.NOT_COMPUTED])
            for text in ("slot tiny", "EMPTY SLOT", "SLOT HELD", "SLOTS FREE"):
                assert_that(text in shown, equal_to(False))
            for text in ("UNRECORDED AGENT", "all full", "TASK LIST in flight"):
                assert_that(text in shown, equal_to(False))

    def test_no_running_option_marks_nothing_queued(self) -> None:
        """The steps of ``slots next`` and of the sweep list keep no queued words."""
        for command in (("slots", "next"), ("sweep",)):
            assert_that(
                slotheld.QUEUED in plain(stale_world(), *command), equal_to(False)
            )

    def test_without_running_a_ruling_is_suggested_and_no_start_is(self) -> None:
        """No slot is known free, so no start, review or fix; the ruling stays."""
        here = flows.world_with(flows.TWO_PLAN_REJECTIONS)
        shown = plain(here, "slots", "next")
        assert_that(shown, contains_string("make an Opus ruling: owner/project#3"))
        assert_that(len(suggestions.parsed(shown)), equal_to(1))
        assert_that(suggestions.parsed(plain(calm(), "slots", "next")), equal_to([]))

    def test_without_running_the_tasks_of_the_rows_are_still_left_out(self) -> None:
        """A ticket a row holds is not offered again, whether or not it runs."""
        shown = plain(stale_world(), "slots", "next")
        assert_that("NEXT 4. owner/project#9" in shown, equal_to(False))

    def test_a_ticket_of_a_finished_agent_is_offered_again(self) -> None:
        """With the agents named, the finished agent's ticket comes back."""
        shown = ran(stale_world(), ("slots", "next"))
        assert_that(shown, contains_string("NEXT 4. owner/project#9"))

    def test_free_without_running_prints_the_rows_and_the_stand_in_line(self) -> None:
        """No refill is computed: the rows as written, then the one line."""
        here = stale_world()
        args = ("slots", "free", here.config, "tiny", "--done", "agent-1")
        lines = world.invoke(here, *args).out.splitlines()
        assert_that(lines[0], starts_with("EMPTY SLOT: tiny"))
        assert_that(lines[-1], equal_to(slotheld.NOT_COMPUTED))

    def test_a_refill_counts_another_slot_whose_agent_is_gone(self) -> None:
        """Slot big records agent-2 on ticket 9, which no longer runs: 9 is offered."""
        here = world.make_world()
        steps = [
            ("failed", "#1", "small"),
            ("failed", "#3", "small"),
            ("set", "big", "agent-2", "#9", "--running", "agent-2"),
            ("set", "tiny", "agent-1", "#50", "--running", "agent-1", "agent-2"),
        ]
        run_all(here, steps)
        args = ("slots", "free", here.config, "tiny", "--done", "agent-1")
        freed = world.invoke(here, *args, "--now", world.FUTURE, "--running")
        refill = freed.out.splitlines()[-1]
        assert_that(refill, starts_with("EMPTY SLOT: tiny (small): start "))
        assert_that(refill, contains_string("owner/project#9 (start a PR"))

    def test_a_slot_the_derivation_empties_is_refused_by_set_until_freed(self) -> None:
        """``set`` reads the rows as written: free the finished agent first."""
        here = stale_world()
        take = (
            "slots",
            "set",
            here.config,
            "tiny",
            "agent-3",
            "#9",
            "--running",
            "agent-3",
        )
        free = ("slots", "free", here.config, "tiny", "--done", "agent-1")
        refused = world.invoke(here, *take)
        later = [world.invoke(here, *each).code for each in (free, take)]
        assert_that([refused.code, *later], equal_to([2, 0, 0]))
        assert_that(refused.err, contains_string("free it first"))

    def test_reading_writes_nothing(self) -> None:
        """The finished agent's row is still in the file after ``slots next``."""
        here = stale_world()
        before = here.ledger.read_text()
        ran(here, ("slots", "next"), "agent-2")
        assert_that(here.ledger.read_text(), equal_to(before))

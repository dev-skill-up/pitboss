"""The held slots come from the running agents, not the ledger (pitboss#94)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, starts_with

from .. import slotheld
from . import decisionline, world
from .liveagents import calm, ran, said
from .test_slot_commands import run_all
from .says import says

NINTH = "owner/project#9"
REFILL = "SLOT tiny NEXT: "


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
        """Nothing runs: both slots are free and ticket 9 is decided again."""
        shown = ran(stale_world(), ("slots", "next"))
        assert_that(shown, contains_string("SLOTS FREE: 2"))
        assert_that(decisionline.of(shown, NINTH), contains_string("WORKER"))

    def test_a_running_agent_the_ledger_lacks_holds_a_slot(self) -> None:
        """agent-2 runs, agent-1 is gone: the decisions are the same (one-path)."""
        alone = ran(stale_world(), ("slots", "next"))
        shown = ran(stale_world(), ("slots", "next"), "agent-2")
        assert_that(decisionline.listed(shown), equal_to(decisionline.listed(alone)))

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
        """The agents are not known: no row and no held slot, the one line instead."""
        for command in (("slots", "show"), ("sweep",)):
            shown = plain(stale_world(), *command)
            said(shown, "slots: not computed", [slotheld.NOT_COMPUTED])
        for command in (("slots", "show"), ("sweep",), ("slots", "next")):
            shown = plain(stale_world(), *command)
            for text in ("slot tiny", "EMPTY SLOT", "UNRECORDED AGENT", "all full"):
                assert_that(text in shown, equal_to(False))

    def test_without_running_the_tasks_of_the_rows_are_still_left_out(self) -> None:
        """A ticket a row holds is not offered again, whether or not it runs."""
        shown = plain(stale_world(), "slots", "next")
        assert_that(decisionline.of(shown, NINTH), equal_to(""))

    def test_free_without_running_prints_the_rows_and_the_stand_in_line(self) -> None:
        """The rows as written, then the refill of the ledger as written."""
        here = stale_world()
        args = ("slots", "free", here.config, "tiny", "--done", "agent-1")
        lines = world.invoke(here, *args).out.splitlines()
        assert_that(lines[0], starts_with("EMPTY SLOT: tiny"))
        assert_that(lines[-1], starts_with(REFILL))

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
        assert_that(refill, starts_with(f"{REFILL}WORKER: {NINTH}: write the code"))

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
        says(refused.err, "free it first")

    def test_reading_writes_nothing(self) -> None:
        """The finished agent's row is still in the file after ``slots next``."""
        here = stale_world()
        before = here.ledger.read_text()
        ran(here, ("slots", "next"), "agent-2")
        assert_that(here.ledger.read_text(), equal_to(before))

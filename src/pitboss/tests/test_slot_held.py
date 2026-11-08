"""A round that holds a slot, and an agent the ledger does not hold (pitboss#291).

The incident of 2026-11-06: the cap was one slot, the fix round of a PR was
resumed in one agent that left no mark the sweep reads, and ``slots next``
printed ``EMPTY SLOT`` and a ``start a PR`` suggestion, so a second worker ran.
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import slotheld
from . import fakes, suggestions, test_flow_sweep as flows, world
from .test_commands import sweep
from .test_owner_repositories import lines_of
from .test_slot_commands import freed_world, next_output, run_all

PROJECT = world.PROJECT
FIRST_NEXT = "NEXT 1. running workers and reviewers: never interrupted, never stopped"
QUEUED = " QUEUED: waits for a free slot; the running agent is never interrupted"
FIX_HELD = "SLOT HELD: owner/project#3 (fix the review)"
CONFLICT_HELD = "SLOT HELD: owner/project#1 (resolve the conflict)"
UNRECORDED = (
    "UNRECORDED AGENT: {name} runs but holds no slot: run slots set SLOT AGENT TICKET"
)


def incident() -> world.World:
    """The incident: cap one, PR 3 in fix the review, PR 1 waiting for a review.

    Returns:
        The world: PR 3 has a review that asks for changes, PR 1 is green and
        clean with no review, ticket 9 can start, and one slot is left.
    """
    here = flows.world_with([flows.graded(flows.APPROVED, flows.CHANGES, 1)])
    head = "1" * 40
    branch = {"sha": head, "ref": "branch-1"}
    here.bodies[f"{PROJECT}/pulls/1"] = fakes.pull_body(1, head=branch)
    here.bodies[fakes.page(f"{PROJECT}/commits/{head}/check-runs")] = {
        "check_runs": [world.GREEN]
    }
    run_all(here, [("remove", "big")])
    return here


def calm() -> world.World:
    """The default world with PR 1 clean, so that no PR holds a slot.

    Returns:
        The world: PR 1 is red, PR 3 waits for a review, ticket 9 can start.
    """
    here = world.make_world()
    branch = {"sha": "1" * 40, "ref": "branch-1"}
    here.bodies[f"{PROJECT}/pulls/1"] = fakes.pull_body(1, head=branch)
    return here


def said(output: str, start: str, wanted: Sequence[str] | int) -> None:
    """Assert the lines that start with some words, or how many there are.

    Args:
        output: what a command printed.
        start: the words.
        wanted: the lines, or their number.
    """
    found = lines_of(output, start)
    assert_that(len(found) if isinstance(wanted, int) else found, equal_to(wanted))


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


def plain(here: world.World, *command: str) -> str:
    """What a command printed, with no ``--running`` given.

    Args:
        here: the world.
        *command: the command's words before the configuration.

    Returns:
        Its output.
    """
    return world.invoke(here, *command, here.config).out


def kinds(output: str) -> Sequence[str]:
    """The headers of the suggestions of an output.

    Args:
        output: what a command printed.

    Returns:
        The headers, in order.
    """
    return [header for header, _ in suggestions.parsed(output)]


class TestARoundHoldsTheSlot(unittest.TestCase):
    """The state of the incident."""

    def test_the_slot_is_held_not_empty(self) -> None:
        """``SLOT HELD`` stands for ``EMPTY SLOT`` and nothing starts."""
        shown = next_output(incident())
        said(shown, "SLOT HELD", [FIX_HELD])
        said(shown, "EMPTY SLOT", 0)

    def test_no_start_and_no_review_is_suggested(self) -> None:
        """Only the round of the PR that holds the slot has a suggestion."""
        headers = kinds(next_output(incident()))
        assert_that(len(headers), equal_to(1))
        assert_that(headers[0], contains_string("fix the review: owner/project#3"))

    def test_the_steps_wait_and_the_running_agent_comes_first(self) -> None:
        """Every step but the held one ends with the queued words."""
        shown = lines_of(next_output(incident()), "NEXT ")
        assert_that(shown[0], equal_to(FIRST_NEXT))
        assert_that(shown[1].startswith("NEXT 2. "), equal_to(True))
        steps = {each.split(" ")[2]: each for each in shown[1:]}
        waits = {name: line.endswith(QUEUED) for name, line in steps.items()}
        held = "owner/project#3"
        assert_that(waits[held], equal_to(False))
        assert_that([v for k, v in waits.items() if k != held], equal_to([True] * 2))

    def test_an_agent_the_ledger_holds_for_the_pr_is_not_counted_twice(self) -> None:
        """A slot recorded for the PR is the PR's slot, and the ledger is full."""
        here = incident()
        run_all(here, [("set", "tiny", "agent-1", "#3", "--running", "agent-1")])
        shown = next_output(here)
        said(shown, "SLOT HELD", 0)
        assert_that(shown, contains_string("slots: the ledger says all full"))
        assert_that(kinds(shown), equal_to([]))

    def test_a_free_slot_is_still_offered(self) -> None:
        """With a second slot the held round takes one and the other starts."""
        here = incident()
        run_all(here, [("add", "spare", "large")])
        shown = next_output(here)
        said(shown, "SLOT HELD", [FIX_HELD])
        said(shown, "EMPTY SLOT", 1)
        assert_that(QUEUED in shown, equal_to(False))

    def test_the_sweep_says_the_slot_is_held(self) -> None:
        """No ``EMPTY SLOT`` line and no ``SLOTS FREE`` line, a held row."""
        swept = sweep(incident()).out
        said(swept, "EMPTY SLOT", 0)
        said(swept, "SLOTS FREE", 0)
        said(swept, "SLOT HELD", [FIX_HELD])

    def test_the_refill_names_what_holds_the_slot(self) -> None:
        """``slots free`` prints the held line when no slot is free for work."""
        _, lines = freed_world([], incident())
        assert_that(lines[-1], equal_to(FIX_HELD))


class TestEveryKindOfRound(unittest.TestCase):
    """The steps that hold a slot, and the ones that do not."""

    def test_a_merge_conflict_holds_a_slot_and_a_plan_revision_does_not(self) -> None:
        """PR 1 of the default world is dirty; PR 3 revises its plan."""
        worlds = (
            world.make_world(),
            flows.world_with([flows.graded(flows.CHANGES, None, 1)]),
        )
        for here in worlds:
            run_all(here, [("remove", "big")])
            said(next_output(here), "SLOT HELD", [CONFLICT_HELD])


class TestOpusIsOutsideTheCap(unittest.TestCase):
    """A ruling is owed first and takes no slot."""

    def test_a_ruling_is_suggested_while_every_slot_is_held(self) -> None:
        """The ruling's suggestion stays, and no start does."""
        here = flows.world_with(flows.TWO_PLAN_REJECTIONS)
        full = [("remove", "big"), ("set", "tiny", "a", "#50", "--running", "a")]
        run_all(here, full)
        headers = kinds(next_output(here))
        assert_that(len(headers), equal_to(1))
        assert_that(headers[0], contains_string("make an Opus ruling: owner/project#3"))


class TestUnrecordedAgents(unittest.TestCase):
    """More live agents than recorded slots: nothing starts."""

    def test_two_agents_and_an_empty_ledger(self) -> None:
        """One line for each, no empty slot and no start suggestion."""
        here = calm()
        shown = ran(here, ("slots", "next"), "agent-1", "agent-2")
        said(
            shown,
            "UNRECORDED AGENT",
            [UNRECORDED.format(name=n) for n in ("agent-1", "agent-2")],
        )
        said(shown, "EMPTY SLOT", 0)
        assert_that(kinds(shown), equal_to([]))

    def test_show_and_the_sweep_say_it_too(self) -> None:
        """The ledger's rows say the empty slots are held."""
        here = calm()
        for command in (("slots", "show"), ("sweep",)):
            shown = ran(here, command, "agent-1", "agent-2")
            said(shown, "UNRECORDED AGENT", 2)
            said(shown, "EMPTY SLOT", 0)
            assert_that(shown, contains_string("empty, but held by work"))

    def test_one_agent_holds_every_empty_slot_until_it_is_recorded(self) -> None:
        """Two empty slots and one unrecorded agent: no start line at all."""
        here = calm()
        shown = ran(here, ("slots", "next"), "a")
        said(shown, "UNRECORDED AGENT", 1)
        said(shown, "EMPTY SLOT", 0)
        assert_that(kinds(shown), equal_to([]))

    def test_recorded_agents_are_not_unrecorded(self) -> None:
        """Live agents that the ledger holds, and none given, say nothing."""
        here = calm()
        run_all(here, [("set", "tiny", "agent-1", "#9", "--running", "agent-1")])
        for running in (("agent-1",), ("agent-1", "agent-1")):
            said(ran(here, ("slots", "show"), *running), "UNRECORDED AGENT", 0)

    def test_a_renamed_agent_is_left_to_gone_agent(self) -> None:
        """``slots check`` shows the rows as written: the name is for GONE AGENT."""
        here = calm()
        run_all(here, [("set", "tiny", "agent-1", "#9", "--running", "agent-1")])
        shown = ran(here, ("slots", "check"), "other")
        said(shown, "UNRECORDED AGENT", 0)
        said(shown, "GONE AGENT", 1)


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

    def test_no_running_option_leaves_the_ledger_as_written(self) -> None:
        """The agents are not known, so the ledger stands."""
        shown = plain(stale_world(), "slots", "show")
        assert_that(shown, contains_string("slot tiny (small): owner/project#9"))

    def test_reading_writes_nothing(self) -> None:
        """The finished agent's row is still in the file after ``slots next``."""
        here = stale_world()
        before = here.ledger.read_text()
        ran(here, ("slots", "next"), "agent-2")
        assert_that(here.ledger.read_text(), equal_to(before))


class TestTheLines(unittest.TestCase):
    """The parts of the occupancy."""

    def test_a_step_waits_only_when_no_slot_is_free_and_it_holds_none(self) -> None:
        """The round of a PR that holds a slot goes on."""
        full = slotheld.Occupancy(free=0, references=frozenset({"a#1"}))
        assert_that(slotheld.waits(full, "a#1"), equal_to(False))
        assert_that(slotheld.waits(full, "a#2"), equal_to(True))
        assert_that(slotheld.waits(slotheld.UNLIMITED, "a#2"), equal_to(False))


class TestRefillAndRecordedRounds(unittest.TestCase):
    """The two branches of a slot that is free or recorded."""

    def test_a_freed_slot_with_nothing_waiting(self) -> None:
        """More slots than tasks: the refill says that no task is waiting."""
        spares = [("add", f"spare-{n}", "small") for n in range(12)]
        _, lines = freed_world(spares, slot="spare-11")
        assert_that(lines[-1], equal_to("no task is waiting"))

    def test_a_round_the_ledger_records_holds_no_second_slot(self) -> None:
        """A slot recorded for PR 3 is its slot: the free one is empty."""
        here = incident()
        run_all(here, [("add", "spare", "large")])
        run_all(here, [("set", "tiny", "agent-1", "#3", "--running", "agent-1")])
        shown = next_output(here)
        said(shown, "SLOT HELD", 0)
        said(shown, "EMPTY SLOT", 1)


class TestTheSweepListWaits(unittest.TestCase):
    """The sweep's ``TASK LIST`` block, with a full ledger and a ready PR."""

    def test_the_running_line_is_line_one_and_the_steps_are_queued(self) -> None:
        """Line 1 is the running agents; PR 3 waits for a review, so it waits."""
        here = calm()
        full = [("remove", "big"), ("set", "tiny", "a", "#50", "--running", "a")]
        run_all(here, full)
        shown = lines_of(ran(here, ("sweep",), "a"), "TASK LIST next ")
        assert_that(shown[0], equal_to(f"TASK LIST next 1. {FIRST_NEXT[8:]}"))
        waiting = [line for line in shown[1:] if "#" in line]
        assert_that(len(waiting) > 0, equal_to(True))
        assert_that(
            [x.endswith(QUEUED) for x in waiting], equal_to([True] * len(waiting))
        )

    def test_the_round_of_a_held_pr_is_not_queued(self) -> None:
        """The fix round of PR 3 holds the slot, so its line does not wait."""
        shown = lines_of(sweep(incident()).out, "TASK LIST next ")
        rounds = [line for line in shown if "owner/project#3" in line]
        assert_that(rounds[0].endswith(QUEUED), equal_to(False))

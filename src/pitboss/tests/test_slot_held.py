"""A round that holds a slot, and an agent the ledger does not hold (pitboss#291).

The incident of 2026-11-06: the cap was one slot, the fix round of a PR was
resumed in one agent that left no mark the sweep reads, and ``slots next``
printed ``EMPTY SLOT`` and a ``start a PR`` suggestion, so a second worker ran.
Under the one path (keyword: one-path) a slot the ledger records holds its item,
which is omitted; an agent the ledger does not record is said by ``slots show``
and the sweep, and changes no decision.
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import decisionline, fakes, suggestions, test_flow_sweep as flows, world
from .liveagents import calm, ran, said
from .test_commands import sweep
from .test_slot_commands import freed_world, next_output, run_all

PROJECT = world.PROJECT
THIRD = "owner/project#3"
FIX = "WORKER: owner/project#3: fix the execution"
UNRECORDED = (
    "UNRECORDED AGENT: {name} runs but holds no slot: run slots set SLOT AGENT TICKET"
)


def incident() -> world.World:
    """The incident: cap one, PR 3 in fix the review, PR 1 waiting for a review.

    Returns:
        The world: PR 3 has a rejected Execution, a ruling and a head that moved
        by an empty commit, PR 1 is green and clean with no review, ticket 9 can
        start, and one slot is left.
    """
    here = flows.unfixed_after_the_ruling()
    head = "1" * 40
    branch = {"sha": head, "ref": "branch-1"}
    here.bodies[f"{PROJECT}/pulls/1"] = fakes.pull_body(1, head=branch)
    here.bodies[fakes.page(f"{PROJECT}/commits/{head}/check-runs")] = {
        "check_runs": [world.GREEN]
    }
    run_all(here, [("remove", "big")])
    return here


def kinds(output: str) -> Sequence[str]:
    """The headers of the suggestions of an output.

    Args:
        output: what a command printed.

    Returns:
        The headers, in order.
    """
    return [header for header, _ in suggestions.parsed(output)]


class TestARoundHoldsTheSlot(unittest.TestCase):
    """The state of the incident (keyword: one-path: what the ledger holds)."""

    def test_an_item_a_slot_holds_is_omitted(self) -> None:
        """Recorded for PR 3, its slot omits it: no decision and no suggestion."""
        here = incident()
        assert_that(decisionline.of(next_output(here), THIRD), contains_string(FIX))
        run_all(here, [("set", "tiny", "agent-1", "#3", "--running", "agent-1")])
        shown = next_output(here)
        assert_that(decisionline.of(shown, THIRD), equal_to(""))
        assert_that(any(THIRD in each for each in kinds(shown)), equal_to(False))

    def test_the_sweep_names_the_empty_slot(self) -> None:
        """An empty slot with no agent the session runs is EMPTY SLOT."""
        said(sweep(incident()).out, "EMPTY SLOT", 1)

    def test_the_refill_takes_the_first_decision(self) -> None:
        """``slots free`` names the first decision its model may take."""
        _, lines = freed_world([], incident())
        first = decisionline.of(next_output(incident()), "owner/project#1")
        said_line = lines[-1].removeprefix("SLOT tiny NEXT: ")
        assert_that(first, contains_string(said_line))


class TestOpusIsOutsideTheCap(unittest.TestCase):
    """A ruling is owed first and takes no slot."""

    def test_a_ruling_is_suggested_while_every_slot_is_held(self) -> None:
        """The ruling's suggestion stays, for an Opus agent and no slot."""
        here = flows.world_with(flows.TWO_PLAN_REJECTIONS)
        full = [("remove", "big"), ("set", "tiny", "a", "#50", "--running", "a")]
        run_all(here, full)
        headers = kinds(next_output(here))
        wanted = f"SUGGESTION 2 of 3: make an Opus ruling: {THIRD}: Opus agent, no slot"
        assert_that(headers[1], equal_to(wanted))


class TestUnrecordedAgents(unittest.TestCase):
    """More live agents than recorded slots: the ledger's rows say so."""

    def test_the_list_is_the_decisions_whatever_runs(self) -> None:
        """Two agents the ledger does not hold change no decision (one-path)."""
        here = calm()
        alone = ran(here, ("slots", "next"))
        shown = ran(here, ("slots", "next"), "agent-1", "agent-2")
        assert_that(decisionline.listed(shown), equal_to(decisionline.listed(alone)))

    def test_show_and_the_sweep_say_it_too(self) -> None:
        """The ledger's rows say the empty slots are held."""
        here = calm()
        for command in (("slots", "show"), ("sweep",)):
            shown = ran(here, command, "agent-1", "agent-2")
            said(shown, "UNRECORDED AGENT", 2)
            said(shown, "EMPTY SLOT", 0)
            assert_that(shown, contains_string("empty, but held by work"))

    def test_one_agent_holds_every_empty_slot_until_it_is_recorded(self) -> None:
        """Two empty slots and one unrecorded agent: no slot is shown empty."""
        here = calm()
        shown = ran(here, ("slots", "show"), "a")
        said(shown, "UNRECORDED AGENT", [UNRECORDED.format(name="a")])
        said(shown, "EMPTY SLOT", 0)

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

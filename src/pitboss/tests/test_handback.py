"""Tests of ``NO HAND-BACK``: a dispatched agent that has said nothing."""

import datetime
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import handback, ledger
from . import world

START = datetime.datetime(2030, 1, 1, tzinfo=datetime.timezone.utc)
MARKER = "NO HAND-BACK"
CASES: Sequence[tuple[str, int, bool, Sequence[str]]] = (
    ("eleven minutes", 11, False, [f"{MARKER} agent-1 (11 minutes)"]),
    ("nine minutes", 9, False, []),
    ("ten minutes", 10, False, []),
    ("eleven minutes, handed back", 11, True, []),
    ("an hour", 60, False, [f"{MARKER} agent-1 (60 minutes)"]),
)


def sweep_lines(here: world.World, minutes: int) -> Sequence[str]:
    """The NO HAND-BACK lines of a sweep some minutes after the agent started.

    Args:
        here: the world.
        minutes: minutes between the start and the sweep.

    Returns:
        The lines.
    """
    later = (START + datetime.timedelta(minutes=minutes)).isoformat()
    result = world.again(here, "sweep", "--now", later)
    return [line for line in result.out.splitlines() if line.startswith(MARKER)]


def held(started: str) -> ledger.Ledger:
    """A ledger whose one slot holds an agent.

    Args:
        started: the agent's start time, or empty.

    Returns:
        The ledger.
    """
    slot = ledger.Slot(name="s", model="m", agent="a", task="t", started=started)
    return ledger.Ledger(slots=(slot,), failed={})


def slots(here: world.World, action: str, *words: str) -> world.Result:
    """Run a ``slots`` action.

    Args:
        here: the world.
        action: the action.
        *words: its words and options.

    Returns:
        What it did.
    """
    return world.invoke(here, "slots", action, here.config, *words)


def start(here: world.World) -> None:
    """Put an agent in a slot at the start time.

    Args:
        here: the world.
    """
    slots(here, "set", "tiny", "agent-1", "#9", "--now", START.isoformat())


class TestNoHandBack(unittest.TestCase):
    """The sweep names a silent agent."""

    def test_sweep(self) -> None:
        """An agent over ten minutes old without a hand-back is listed."""
        for name, minutes, heard, expected in CASES:
            with self.subTest(name):
                here = world.make_world()
                start(here)
                if heard:
                    slots(here, "heard", "tiny", "--now", START.isoformat())
                assert_that(sweep_lines(here, minutes), equal_to(expected))

    def test_freed_agent(self) -> None:
        """A freed slot (the hand-back arrived) lists nothing."""
        here = world.make_world()
        start(here)
        slots(here, "free", "tiny")
        assert_that(sweep_lines(here, 60), equal_to([]))

    def test_unstarted_agent(self) -> None:
        """An entry with no start time (an old ledger) lists nothing."""
        assert_that(handback.lines(held(""), START), equal_to([]))

    def test_naive_clock(self) -> None:
        """A clock with no zone is taken as UTC."""
        book = ledger.stamp(held(""), "s", ledger.Mark.STARTED, "2030-01-01T00:00:00")
        assert isinstance(book, ledger.Ledger)
        later = datetime.datetime(2030, 1, 1, 0, 12)
        assert_that(handback.lines(book, later), equal_to([f"{MARKER} a (12 minutes)"]))


class TestHeardRefusal(unittest.TestCase):
    """Hearing from an empty slot is refused."""

    def test_empty_slot(self) -> None:
        """An empty slot has no agent to hear from."""
        here = world.make_world()
        result = slots(here, "heard", "tiny")
        assert_that(
            (result.code, result.err.splitlines()[-1]),
            equal_to((2, "refused: slot tiny is empty: set an agent first")),
        )

    def test_no_such_slot(self) -> None:
        """A slot that does not exist is refused."""
        refused = ledger.stamp(
            ledger.Ledger(slots=(), failed={}), "x", ledger.Mark.HEARD, "now"
        )
        assert_that(isinstance(refused, ledger.Refusal), equal_to(True))

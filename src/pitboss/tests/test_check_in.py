"""Tests of ``IDLE SLOT`` and ``CHECK-IN OVERDUE`` (keyword: free-check, check-in)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, starts_with

from . import world
from .test_handback import slots, start
from .test_quiet import at
from .test_slot_idle import emptied

IDLE = "IDLE SLOT: free for {} minutes, next is "
LATE = "CHECK-IN OVERDUE: last {} minutes ago"


def checked_in() -> world.World:
    """A world whose orchestrator checked in at the start time.

    Returns:
        The world.
    """
    here = world.make_world()
    slots(here, "checkin", "--now", world.START.isoformat())
    return here


def first_line(here: world.World, minute: int, *argv: str) -> str:
    """The first line a command prints at a minute.

    Args:
        here: the world.
        minute: minutes after the start.
        *argv: the command and its options, the config after the first word.

    Returns:
        The line, or empty when the command prints nothing.
    """
    name, *rest = argv
    out = world.invoke(here, name, *rest[:1], here.config, *rest[1:], *at_(minute))
    return next(iter(out.out.splitlines()), "")


def at_(minute: int) -> Sequence[str]:
    """The ``--now`` option of a minute.

    Args:
        minute: minutes after the start.

    Returns:
        The two words.
    """
    return ("--now", at(minute))


class TestFreeCheck(unittest.TestCase):
    """``slots free-check`` names a slot free for over ten minutes."""

    def test_the_line_by_minutes(self) -> None:
        """Eleven minutes prints the line; ten, or a held slot, nothing."""
        held = world.make_world()
        start(held)
        cases = [(emptied(), 11, True), (emptied(), 10, False), (held, 5, False)]
        for here, minute, told in cases:
            out = slots(here, "free-check", *at_(minute)).out
            assert_that(out.startswith(IDLE.format(minute)), equal_to(told))
            assert_that(out == "", equal_to(not told))

    def test_next_line_is_named(self) -> None:
        """The line carries the slots next command of the first item."""
        out = slots(emptied(), "free-check", *at_(11)).out
        assert_that(out, contains_string("pitboss slots next"))

    def test_sweep_starts_with_the_line(self) -> None:
        """A sweep prints the line first when it applies, and not at nine."""
        here = emptied()
        assert_that(first_line(here, 11, "sweep"), starts_with(IDLE.format(11)))
        assert_that(
            first_line(here, 9, "sweep").startswith("IDLE SLOT"), equal_to(False)
        )


class TestCheckIn(unittest.TestCase):
    """The ledger keeps the time of each check-in."""

    def test_next_and_sweep_by_minutes(self) -> None:
        """Over thirty minutes both print the line first; thirty, none."""
        here = checked_in()
        for argv in (("slots", "next"), ("sweep",)):
            assert_that(first_line(here, 31, *argv), equal_to(LATE.format(31)))
            assert_that(
                first_line(here, 30, *argv).startswith("CHECK-IN"), equal_to(False)
            )

    def test_sweep_overdue_fails(self) -> None:
        """A sweep thirty-one minutes after the check-in exits non-zero."""
        here = checked_in()
        assert_that(
            world.invoke(here, "sweep", here.config, *at_(31)).code, equal_to(1)
        )

    def test_none_recorded_or_renewed(self) -> None:
        """No check-in recorded, or a new one, leaves no lapse."""
        renewed = checked_in()
        slots(renewed, "checkin", *at_(31))
        for here, minute in ((world.make_world(), 300), (renewed, 40)):
            line = first_line(here, minute, "slots", "next")
            assert_that(line.startswith("CHECK-IN"), equal_to(False))


class TestStatusPrompt(unittest.TestCase):
    """The check-in prompt names the status post and the fresh schedule."""

    def test_prompt(self) -> None:
        """The prompt names its parts and the config."""
        here = world.make_world()
        out = world.invoke(here, "status-prompt", here.config).out
        for part in (
            "what holds each slot",
            "what changed",
            "what is blocked on what",
            "next due",
            "expires",
            "Recreate your own schedule fresh",
            "slots checkin --config " + here.config,
        ):
            assert_that(out, contains_string(part))

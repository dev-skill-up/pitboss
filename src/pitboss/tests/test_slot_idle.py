"""Tests of ``SLOT IDLE``."""

import re
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import liveagents, world
from .test_commands import clear_queue
from .test_handback import slots, start
from .test_quiet import at

START = world.START
TINY_IDLE = re.compile(r"^SLOT IDLE tiny \((\d+) minutes\)", re.MULTILINE)


def minutes_idle(here: world.World, minutes: int) -> Sequence[str]:
    """The minutes ``tiny`` is said idle in a sweep some minutes after the start.

    The world's other slot, ``big``, is logged empty when ``tiny`` is set, so it
    is idle too and is left out here.

    Args:
        here: the world.
        minutes: minutes between the start and the sweep.

    Returns:
        The minutes of each ``SLOT IDLE tiny`` line.
    """
    args = ("sweep", here.config, "--now", at(minutes), *liveagents.running(here))
    out = world.invoke(here, *args).out
    return TINY_IDLE.findall(out)


def emptied() -> world.World:
    """A world whose slot ``tiny`` was filled and freed at the start time.

    Returns:
        The world, with work queued.
    """
    here = world.make_world()
    start(here)
    slots(here, "free", "tiny", "--done", "agent-1", "--now", START.isoformat())
    return here


def emptied_without_work() -> world.World:
    """The same world with no ticket and no pull request to start.

    Returns:
        The world.
    """
    here = emptied()
    clear_queue(here)
    return here


class TestSlotIdle(unittest.TestCase):
    """The sweep names a slot that stayed empty while work was ready."""

    def test_empty_five_minutes_with_work(self) -> None:
        """A slot empty for 5 minutes with a ready ticket is named."""
        assert_that(minutes_idle(emptied(), 5), equal_to(["5"]))

    def test_empty_one_minute(self) -> None:
        """A slot empty for 1 minute is not yet idle."""
        assert_that(minutes_idle(emptied(), 1), equal_to([]))

    def test_exactly_two_minutes(self) -> None:
        """Two minutes is not over two minutes."""
        assert_that(minutes_idle(emptied(), 2), equal_to([]))

    def test_full_slot(self) -> None:
        """A slot with an agent is never idle."""
        here = world.make_world()
        start(here)
        assert_that(minutes_idle(here, 5), equal_to([]))

    def test_nothing_queued(self) -> None:
        """An empty slot with no work to start is not idle."""
        assert_that(minutes_idle(emptied_without_work(), 5), equal_to([]))

    def test_slot_the_log_never_saw(self) -> None:
        """A slot with no entry in the log has no time to tell."""
        assert_that(minutes_idle(world.make_world(), 5), equal_to([]))

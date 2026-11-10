"""How fast the watcher polls and how often a free slot is said again (#415)."""

import contextlib
import io
import unittest
from typing import Callable, Sequence

from hamcrest import assert_that, equal_to

from .. import config, configfile, watchrun
from . import watchworld, world


def played(free: Sequence[bool], every: int) -> tuple[str, Sequence[float]]:
    """Run the loop over some rounds, free or not, with a recording sleeper.

    Args:
        free: for each round, whether a slot is free after it.
        every: the rounds between two ``SLOT FREE`` lines.

    Returns:
        What was printed and the waits.
    """
    rounds = iter(range(1, len(free) + 1))
    slept: list[float] = []

    def one() -> watchrun.Report:
        number = next(rounds)
        line: Callable[[], str] = lambda: f"FREE after round {number}"
        return watchrun.Report(said=[], free=free[number - 1], free_line=line)

    pace = watchrun.Pace(interval=15, every=every, sleep=slept.append)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        watchrun.loop(one, pace, len(free))
    return out.getvalue(), slept


class TestLoop(unittest.TestCase):
    """The lines of the rounds, by whether the slot stays free."""

    def test_a_free_slot_is_said_from_the_second_round_and_every_few_after(
        self,
    ) -> None:
        """Rounds 2, 5 and 8 of eight free rounds when it is said every three."""
        out, slept = played([True] * 8, 3)
        assert_that(
            (out.splitlines(), slept),
            equal_to(
                (
                    ["FREE after round 2", "FREE after round 5", "FREE after round 8"],
                    [15] * 7,
                )
            ),
        )

    def test_an_agent_that_fills_the_slot_stops_the_line_and_resets_the_count(
        self,
    ) -> None:
        """A busy round in between: the count of free rounds starts again."""
        out, _ = played([True, True, False, True, True, True], 1)
        assert_that(
            out.splitlines(),
            equal_to(
                ["FREE after round 2", "FREE after round 5", "FREE after round 6"]
            ),
        )


class TestPace(unittest.TestCase):
    """The configuration's keys and the option."""

    def test_the_defaults_are_fifteen_seconds_and_five_minutes(self) -> None:
        """Every twentieth round says the slot is still free."""
        found = watchrun.pace_of(config.Watch(), None)
        assert_that((found.interval, found.every), equal_to((15, 20)))

    def test_the_keys_and_the_option(self) -> None:
        """poll-seconds and remind-minutes; ``--interval`` replaces the poll."""
        kept = config.Watch(poll_seconds=60, remind_minutes=2)
        found = [watchrun.pace_of(kept, given) for given in (None, 30, 0)]
        assert_that(
            [(each.interval, each.every) for each in found],
            equal_to([(60, 2), (30, 4), (0, 1)]),
        )

    def test_the_keys_are_read_from_the_slots_table(self) -> None:
        """A configuration that sets them, and one that does not."""
        both = ("poll-seconds = 30\nremind-minutes = 2\n", "")
        kept = map(watch_keys, watchworld.planted_each(both))
        assert_that(list(kept), equal_to([(30, 2), (15, 5)]))


def watch_keys(here: world.World) -> tuple[int, int]:
    """The poll and reminder keys a world's configuration holds.

    Args:
        here: the world.

    Returns:
        The seconds between polls and the minutes between reminders.
    """
    slots = configfile.load(here.config, start=here.workspace).slots
    return slots.watch.poll_seconds, slots.watch.remind_minutes


class TestFailure(unittest.TestCase):
    """A round that cannot read or write says so before it exits."""

    def test_an_unreadable_ledger_prints_watch_failed_and_exits_one(self) -> None:
        """The ledger is a directory."""
        here, _ = watchworld.watched()
        here.ledger.unlink()
        here.ledger.mkdir()
        made = watchworld.watch(here)
        assert_that(
            (made.code, made.out.startswith("WATCH FAILED: ")), equal_to((1, True))
        )

"""Tests for the slot log: a fixed log replayed, and how the log is kept."""

import datetime
import json
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import ledger, slotlog
from . import fakes

DAY = "2030-01-01"
FIXED_LOG = (
    '{"time": "2030-01-01T00:00:00+00:00", "slot": "a", "state": "running",'
    ' "agent": "w1", "task": "o/r#1"}',
    '{"time": "2030-01-01T00:00:00+00:00", "slot": "b", "state": "empty",'
    ' "agent": "", "task": ""}',
    '{"time": "2030-01-01T01:00:00+00:00", "slot": "a", "state": "waiting",'
    ' "agent": "w1", "task": "o/r#1"}',
    '{"time": "2030-01-01T02:00:00+00:00", "slot": "a", "state": "empty",'
    ' "agent": "", "task": ""}',
    '{"time": "2030-01-01T02:00:00+00:00", "slot": "b", "state": "running",'
    ' "agent": "w2", "task": "o/r#2"}',
    '{"time": "2030-01-01T03:00:00", "slot": "b", "state": "removed",'
    ' "agent": "", "task": ""}',
)
WHOLE = [
    "slot time 2030-01-01T00:00:00+00:00 to 2030-01-01T04:00:00+00:00",
    "slot a: running 25.0%, waiting 25.0%, empty 50.0% of 14400 s",
    "slot b: running 33.3%, waiting 0.0%, empty 66.7% of 10800 s",
    "all slots: running 28.6%, waiting 14.3%, empty 57.1% of 25200 s",
]
MIDDLE = [
    "slot time 2030-01-01T01:00:00+00:00 to 2030-01-01T03:00:00+00:00",
    "slot a: running 0.0%, waiting 50.0%, empty 50.0% of 7200 s",
    "slot b: running 50.0%, waiting 0.0%, empty 50.0% of 7200 s",
    "all slots: running 25.0%, waiting 25.0%, empty 50.0% of 14400 s",
]


def at(hour: int) -> datetime.datetime:
    """A time of the fixed day.

    Args:
        hour: the hour.

    Returns:
        The time, in UTC.
    """
    return datetime.datetime(2030, 1, 1, hour, tzinfo=datetime.timezone.utc)


def fixed_log() -> Sequence[slotlog.Entry]:
    """Read the fixed log from a file.

    Returns:
        Its entries.
    """
    path = fakes.directory() / "slots.log"
    path.write_text("\n".join(FIXED_LOG) + "\n")
    return slotlog.read(path)


class TestReplay(unittest.TestCase):
    """The proportions of slot time in each state."""

    def test_whole_window(self) -> None:
        """Running, waiting and empty time are each a share of all slot time."""
        assert_that(slotlog.lines(fixed_log(), at(0), at(4)), equal_to(WHOLE))

    def test_inner_window(self) -> None:
        """A window cuts the intervals it starts or ends inside."""
        assert_that(slotlog.lines(fixed_log(), at(1), at(3)), equal_to(MIDDLE))

    def test_no_time(self) -> None:
        """A window with no slot time says so."""
        before = at(0) - datetime.timedelta(days=2)
        expected = [
            "slot time 2029-12-30T00:00:00+00:00 to 2029-12-30T01:00:00+00:00: none"
        ]
        found = slotlog.lines(fixed_log(), before, before + datetime.timedelta(hours=1))
        assert_that(found, equal_to(expected))
        assert_that(slotlog.lines((), at(0), at(1))[0].endswith("none"), equal_to(True))


class TestKeeping(unittest.TestCase):
    """What is logged, and when."""

    def test_changes_and_append(self) -> None:
        """Only a slot that differs from its last entry, or is gone, is logged."""
        slots = (ledger.Slot(name="a", model="m"), ledger.Slot(name="b", model="m"))
        book = ledger.Ledger(slots=slots, failed={})
        first = slotlog.changes((), book, at(1))
        assert_that([e.state for e in first], equal_to([slotlog.State.EMPTY] * 2))
        assert_that(slotlog.changes(first, book, at(2)), equal_to([]))
        busy = ledger.Ledger(
            slots=(
                ledger.Slot(name="a", model="m", agent="w", task="t", waiting=True),
            ),
            failed={},
        )
        later = slotlog.changes(first, busy, at(3))
        assert_that(
            [(e.slot, e.state) for e in later],
            equal_to([("a", slotlog.State.WAITING), ("b", slotlog.State.REMOVED)]),
        )
        assert_that(slotlog.changes([*first, *later], busy, at(4)), equal_to([]))
        path = fakes.directory() / "slots.log"
        slotlog.append(path, later)
        slotlog.append(path, first)
        assert_that(slotlog.read(path), equal_to([*later, *first]))
        assert_that(
            json.loads(path.read_text().splitlines()[0])["state"], equal_to("waiting")
        )

    def test_read_missing_and_zones(self) -> None:
        """No file is no entries; a time with no zone is UTC; others convert."""
        assert_that(slotlog.read(pathlib.Path("/nonexistent/slots.log")), equal_to(()))
        naive = datetime.datetime(2030, 1, 1, 3)
        assert_that(slotlog.utc(naive), equal_to(at(3)))
        zone = datetime.timezone(datetime.timedelta(hours=2))
        assert_that(
            slotlog.utc(datetime.datetime(2030, 1, 1, 5, tzinfo=zone)), equal_to(at(3))
        )

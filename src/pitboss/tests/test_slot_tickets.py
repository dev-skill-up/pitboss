"""The ticket and kind of a slot's task, and the worker time per ticket."""

import dataclasses
import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import ledger
from . import world
from .test_slot_commands import run_all

UNTIL = ("--until", "2030-01-01T04:00:00")
TICKET_9 = "owner/project#9"
NOT_A_REFERENCE = "cannot name the ticket of 'x': it is not owner/name#number"
NO_FIXES = "cannot name the ticket of owner/project#2: its body has no Fixes line"
UNREADABLE = (
    "cannot name the ticket of owner/project#77:"
    " repos/owner/project/issues/77 cannot be read"
)
UNNAMED = (("x", NOT_A_REFERENCE), ("#2", NO_FIXES), ("#77", UNREADABLE))


def at(hour: int, minute: int = 0) -> str:
    """A time of the day the tests use.

    Args:
        hour: the hour.
        minute: the minute.

    Returns:
        The ISO time, in UTC.
    """
    return f"2030-01-01T{hour:02d}:{minute:02d}:00+00:00"


TIME_STEPS = (
    ("set", "tiny", "agent-1", "#3", "--kind", "review", "--now", at(0))
    + ("--running", "agent-1"),
    ("set", "big", "agent-2", "lib#1", "--now", at(0))
    + ("--running", "agent-1", "agent-2"),
    ("wait", "tiny", "--now", at(1)),
    ("free", "big", "--done", "agent-2", "--now", at(1)),
    ("resume", "tiny", "--now", at(2)),
    ("set", "tiny", "agent-1", "#3", "--kind", "fix", "--now", at(2, 30))
    + ("--running", "agent-1"),
    ("free", "tiny", "--done", "agent-1", "--now", at(3)),
)
WHOLE = [
    f"worker time per ticket {at(0)} to {at(4)}",
    "ticket owner/lib#1: 60.0 min in 1 entries",
    "ticket owner/project#9: 120.0 min in 2 entries",
    "median 90.0 min, mean 90.0 min over 2 tickets",
]
LATE = [
    f"worker time per ticket {at(1, 30)} to {at(4)}",
    "ticket owner/project#9: 60.0 min in 1 entries",
    "median 60.0 min, mean 60.0 min over 1 tickets",
]
NONE = f"worker time per ticket {at(0)} to {at(1)}: none"


def logged(here: world.World) -> Sequence[Mapping[str, object]]:
    """The slot log's lines.

    Args:
        here: the world.

    Returns:
        Each line as the JSON it is.
    """
    log = here.ledger.with_suffix(".log")
    return [json.loads(line) for line in log.read_text().splitlines()]


def slot_of(here: world.World, name: str) -> Mapping[str, object]:
    """A slot as the ledger file keeps it, with absent fields empty.

    Args:
        here: the world.
        name: the slot's name.

    Returns:
        The slot's JSON.
    """
    book = ledger.read(here.ledger, ())
    return dataclasses.asdict(next(s for s in book.slots if s.name == name))


def times(here: world.World, *window: str) -> Sequence[str]:
    """The lines of ``slots time``, without a warning about the world.

    Args:
        here: the world.
        *window: the arguments after the config.

    Returns:
        The lines from its heading on.
    """
    lines = world.invoke(here, "slots", "time", here.config, *window).out
    return [line for line in lines.splitlines() if "UNREADABLE" not in line]


class TestField(unittest.TestCase):
    """``slots set`` records the ticket and the kind."""

    def test_ticket_and_kind(self) -> None:
        """A ticket is its own ticket; the kind is start unless it is given."""
        here = world.make_world()
        run_all(here, [("set", "tiny", "agent-1", "#9", "--running", "agent-1")])
        slot = slot_of(here, "tiny")
        assert_that(
            (slot["task"], slot["ticket"], slot["kind"]),
            equal_to((TICKET_9, TICKET_9, "start")),
        )
        entry = logged(here)[0]
        assert_that(
            (entry["ticket"], entry["kind"], entry["begun"]),
            equal_to((TICKET_9, "start", True)),
        )

    def test_pull_request_resolves_to_its_first_fixes(self) -> None:
        """A PR's ticket is the first Fixes line of its body, in any repository."""
        here = world.make_world()
        review = ("set", "tiny", "agent-1", "#3", "--kind", "review")
        run_all(here, [review + ("--running", "agent-1")])
        ruling = ("set", "big", "agent-2", "lib#4", "--kind", "ruling")
        run_all(here, [ruling + ("--running", "agent-1", "agent-2")])
        found = [(slot_of(here, name)["ticket"]) for name in ("tiny", "big")]
        assert_that(found, equal_to([TICKET_9, TICKET_9]))
        assert_that(slot_of(here, "big")["kind"], equal_to("ruling"))

    def test_slots_made_before_the_fields(self) -> None:
        """A slot of an older ledger has the fields empty and is set as any."""
        here = world.make_world()
        shown, taken = run_all(here, [("show",), ("set", "tiny", "agent-1", "#9", "--running", "x")])
        assert_that((shown.code, taken.code), equal_to((0, 0)))
        assert_that(slot_of(here, "big")["ticket"], equal_to(""))


class TestRefusal(unittest.TestCase):
    """``slots set`` refuses an id whose ticket it cannot name."""

    def test_unnamed_ticket(self) -> None:
        """Not a reference, no Fixes line, and an unreadable id are refused."""
        for task, reason in UNNAMED:
            with self.subTest(task):
                here = world.make_world()
                (result,) = run_all(here, [("set", "tiny", "agent-1", task, "--running", "x")])
                assert_that(
                    (result.code, result.err.splitlines()[-1]),
                    equal_to((2, f"refused: {reason}")),
                )
                assert_that(slot_of(here, "tiny")["agent"], equal_to(""))


class TestFixRound(unittest.TestCase):
    """A fix round resumes a running agent and is an entry too."""

    def test_same_agent_fix(self) -> None:
        """The same agent may be set again for a fix; no other set may."""
        here = world.make_world()
        steps = [
            ("set", "tiny", "agent-1", "#3", "--now", at(0)),
            ("set", "tiny", "agent-1", "#3", "--kind", "fix", "--now", at(1)),
            ("set", "tiny", "agent-2", "#3", "--kind", "fix", "--now", at(2)),
            ("set", "tiny", "agent-1", "#3", "--kind", "review", "--now", at(2)),
        ]
        steps = [step + ("--running", "agent-1", "agent-2") for step in steps]
        results = run_all(here, steps)
        assert_that([result.code for result in results], equal_to([0, 0, 2, 2]))
        entries = [(item["kind"], item["begun"]) for item in logged(here)]
        assert_that(
            entries[:3], equal_to([("start", True), ("", False), ("fix", True)])
        )
        assert_that(slot_of(here, "tiny")["kind"], equal_to("fix"))


class TestTime(unittest.TestCase):
    """``slots time`` totals worker minutes per ticket."""

    def test_report(self) -> None:
        """Start, review, fix and ruling entries sum per ticket, with the median."""
        here = world.make_world()
        run_all(here, TIME_STEPS)
        assert_that(times(here, *UNTIL), equal_to(WHOLE))

    def test_since(self) -> None:
        """A window cuts the entries it starts inside."""
        here = world.make_world()
        run_all(here, TIME_STEPS)
        window = ("--since", at(1, 30), *UNTIL)
        assert_that(times(here, *window), equal_to(LATE))

    def test_no_log(self) -> None:
        """A window with no worker time says so, and needs no ledger."""
        here = world.make_world()
        here.ledger.unlink()
        window = ("--since", at(0), "--until", at(1))
        assert_that(times(here, *window), equal_to([NONE]))

    def test_words(self) -> None:
        """Words are refused."""
        (result,) = run_all(world.make_world(), [("time", "extra")])
        assert_that(result.err.splitlines()[-1], equal_to("slots time takes no words"))

"""End-to-end tests of ``slots``: a fake GitHub, a real ledger file."""

import json
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from . import world

LEDGER_STEPS = (
    ("set", "tiny", "agent-1", "#9"),
    ("add", "spare", "large"),
    ("remove", "big"),
    ("set", "spare", "agent-2", "lib#1"),
    ("check", "--running", "agent-2"),
    ("free", "tiny"),
    ("failed", "#9", "small"),
    ("show",),
)
CHECK_LINES = [
    "GONE AGENT: slot tiny holds agent-1, which is not running:"
    " 'pitboss slots free {config} tiny'",
    "slot tiny (small): owner/project#9 (agent-1)",
    "slot spare (large): owner/lib#1 (agent-2)",
    "slots: the ledger says all full",
]
REFUSAL_STEPS = (
    ("set", "tiny"),
    ("show", "extra"),
    ("set", "tiny", "agent-1", "#9"),
    ("set", "tiny", "agent-2", "#9"),
)
REFUSALS = [
    (2, "slots set takes 3 words"),
    (2, "slots show takes no words"),
    (0, "CHECK BEFORE YOU ANSWER"),
    (2, "refused: slot tiny holds agent-1 on owner/project#9: free it first"),
]
NEXT_TWO = ["NEXT 1. owner/project#3", "NEXT 2. owner/project#9"]
TICKET_LINE = (
    "EMPTY SLOT: tiny (small): start owner/project#9 (start a PR urgent,"
    " opened 2026-09-01, 1218 days, smallest model small): A ticket"
)
REVIEW_LINE = (
    "EMPTY SLOT: big (large): start owner/project#3 (review it (a reviewer that"
    " is not its author), opened 2026-10-01, 1188 days, smallest model large): PR 3"
)
NEXT_CASES: Sequence[tuple[Sequence[Sequence[str]], Sequence[str]]] = [
    ([("failed", "#3", "small")], [*NEXT_TWO, TICKET_LINE, REVIEW_LINE]),
    (
        [("set", "tiny", "a", "x"), ("set", "big", "b", "y")],
        [*NEXT_TWO, "slots: the ledger says all full: start nothing"],
    ),
    (
        [("remove", "big"), ("failed", "#9", "small"), ("failed", "#3", "small")],
        [*NEXT_TWO, "EMPTY SLOT: tiny (small): nothing fits it: leave it empty"],
    ),
]
MARKERS = ("NEXT", "EMPTY SLOT", "slots:")


def run_all(
    here: world.World, steps: Sequence[Sequence[str]]
) -> Sequence[world.Result]:
    """Run ``slots`` commands in order.

    Args:
        here: the world.
        steps: each command's words after ``slots``, the action first.

    Returns:
        What each did.
    """
    return [
        world.invoke(here, "slots", words[0], here.config, *words[1:])
        for words in steps
    ]


def next_output(here: world.World) -> str:
    """What ``slots next`` prints.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    return world.invoke(here, "slots", "next", here.config, "--now", world.FUTURE).out


def next_lines(here: world.World) -> Sequence[str]:
    """The lines of ``slots next`` that start with a marker, a NEXT line cut short.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    lines = [
        line for line in next_output(here).splitlines() if line.startswith(MARKERS)
    ]
    return [line.split(" (")[0] if line.startswith("NEXT") else line for line in lines]


class TestLedger(unittest.TestCase):
    """Keeping the ledger."""

    def test_ledger(self) -> None:
        """Slots are taken, added, removed, checked, freed and failed."""
        here = world.make_world()
        results = run_all(here, LEDGER_STEPS)
        expected = [line.format(config=here.config) for line in CHECK_LINES]
        assert_that(results[4].out.splitlines()[-4:], equal_to(expected))
        assert_that('"owner/project#9"' in here.ledger.read_text(), equal_to(True))
        assert_that(results[-1].out.count("EMPTY SLOT: tiny"), equal_to(1))

    def test_refusals(self) -> None:
        """A wrong word count or a refused change exits 2 and says why."""
        results = run_all(world.make_world(), REFUSAL_STEPS)
        found = [
            (result.code, result.err.splitlines()[-1][: len(line)])
            for result, (_, line) in zip(results, REFUSALS)
        ]
        assert_that(found, equal_to(REFUSALS))


WAIT_STEPS = (
    ("wait", "nosuch"),
    ("wait", "tiny"),
    ("set", "tiny", "agent-1", "#9"),
    ("wait", "tiny"),
    ("show",),
    ("resume", "tiny"),
    ("free", "tiny"),
)
LOG_STEPS = (
    ("set", "tiny", "agent-1", "#9", "--now", "2030-01-01T00:00:00+00:00"),
    ("wait", "tiny", "--now", "2030-01-01T01:00:00+00:00"),
    ("free", "tiny", "--now", "2030-01-01T02:00:00+00:00"),
    ("remove", "big", "--now", "2030-01-01T03:00:00+00:00"),
)
LOG_LINES = [
    ("tiny", "running", "00"),
    ("big", "empty", "00"),
    ("tiny", "waiting", "01"),
    ("tiny", "empty", "02"),
    ("big", "removed", "03"),
]
REPORT_LINES = [
    "slot time 2030-01-01T00:00:00+00:00 to 2030-01-01T04:00:00+00:00",
    "slot big: running 0.0%, waiting 0.0%, empty 100.0% of 10800 s",
    "slot tiny: running 25.0%, waiting 25.0%, empty 50.0% of 14400 s",
    "all slots: running 14.3%, waiting 14.3%, empty 71.4% of 25200 s",
]


class TestLog(unittest.TestCase):
    """The slot log, waiting, and the report."""

    def test_wait_and_resume(self) -> None:
        """An empty slot cannot wait; the show line says a waiting agent waits."""
        here = world.make_world()
        results = run_all(here, WAIT_STEPS)
        assert_that(results[0].code, equal_to(2))
        assert_that(results[1].code, equal_to(2))
        assert_that(
            results[4].out.splitlines()[1],
            equal_to("slot tiny (small): owner/project#9 (agent-1, waiting)"),
        )
        assert_that(results[-1].code, equal_to(0))

    def test_log(self) -> None:
        """Each change of a slot's state is a log line."""
        here = world.make_world()
        run_all(here, LOG_STEPS)
        log = here.ledger.with_suffix(".log")
        lines = [json.loads(line) for line in log.read_text().splitlines()]
        found = [(item["slot"], item["state"], item["time"][11:13]) for item in lines]
        assert_that(found, equal_to(LOG_LINES))

    def test_report(self) -> None:
        """The report gives the shares of a window; a window before it has none."""
        here = world.make_world()
        run_all(here, LOG_STEPS)
        until = ("--until", "2030-01-01T04:00:00")
        report = world.invoke(here, "slots", "report", here.config, *until)
        assert_that(report.out.splitlines()[1:], equal_to(REPORT_LINES))
        window = ("--since", "2029-12-30", "--until", "2029-12-31")
        empty = world.invoke(here, "slots", "report", here.config, *window)
        assert_that(empty.out.strip().endswith("none"), equal_to(True))

    def test_report_without_log_and_with_words(self) -> None:
        """No log is no slot time; words are refused."""
        here = world.make_world()
        result = world.invoke(
            here, "slots", "report", here.config, "--now", world.FUTURE
        )
        assert_that(result.out.strip().endswith("none"), equal_to(True))
        refused = world.invoke(here, "slots", "report", here.config, "extra")
        assert_that(
            (refused.code, refused.err.splitlines()[-1]),
            equal_to((2, "slots report takes no words")),
        )


class TestNext(unittest.TestCase):
    """What to start next."""

    def test_cases(self) -> None:
        """The list is sorted; each empty slot takes what it may, or nothing."""
        for steps, expected in NEXT_CASES:
            here = world.make_world()
            run_all(here, steps)
            assert_that(next_lines(here), equal_to(expected))

"""End-to-end tests of ``slots``: a fake GitHub, a real ledger file."""

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


def next_lines(here: world.World) -> Sequence[str]:
    """The lines of ``slots next`` that start with a marker, a NEXT line cut short.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    result = world.invoke(here, "slots", "next", here.config, "--now", world.FUTURE)
    lines = [line for line in result.out.splitlines() if line.startswith(MARKERS)]
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
            (result.code, result.err.splitlines()[0][: len(line)])
            for result, (_, line) in zip(results, REFUSALS)
        ]
        assert_that(found, equal_to(REFUSALS))


class TestNext(unittest.TestCase):
    """What to start next."""

    def test_cases(self) -> None:
        """The list is sorted; each empty slot takes what it may, or nothing."""
        for steps, expected in NEXT_CASES:
            here = world.make_world()
            run_all(here, steps)
            assert_that(next_lines(here), equal_to(expected))

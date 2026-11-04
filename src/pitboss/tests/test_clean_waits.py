"""A clean PR at a wait keeps it: no review and no CI fix is offered (pitboss#183).

The draft gate and the CI gate of ``flow.next_step`` answer before the rejection
step, so a clean draft PR at RULING DUE or PAUSE, and a clean PR with red CI at
RULING ESCALATES, must still get the wait of the rejection and be offered for
no round: ``slots next`` prints the wait line and no NEXT line for each.
"""

import unittest

from hamcrest import assert_that, equal_to

from . import fakes, test_conflict_waits as waits, test_flow_sweep as flows, world
from .test_commands import sweep

DUE = "ruling due after two plan rejections"
PAUSE = "pause after a ruling and another rejection"
ESCALATES = "the ruling escalates"


def clean(name: str, **changes: object) -> tuple[world.World, str]:
    """A clean PR 3 at a wait of the conflict tests.

    Args:
        name: the wait, a key of ``test_conflict_waits.WAITING``.
        **changes: changes to PR 3's JSON (``draft``).

    Returns:
        The world, and the start of the wait's line.
    """
    rounds, line = waits.WAITING[name]
    return flows.world_with(rounds, **changes), line


def red(name: str) -> tuple[world.World, str]:
    """A clean PR 3 at a wait of the conflict tests, with red CI.

    Args:
        name: the wait, a key of ``test_conflict_waits.WAITING``.

    Returns:
        The world, and the start of the wait's line.
    """
    here, line = clean(name)
    path = fakes.page(f"{world.PROJECT}/commits/{flows.HEAD}/check-runs")
    here.bodies[path] = {"check_runs": [world.RED]}
    return here, line


class TestCleanWaits(unittest.TestCase):
    """The gates above the rejection step do not hide a wait."""

    def test_a_clean_pr_at_a_wait_prints_the_wait_and_no_next_line(self) -> None:
        """A draft at RULING DUE, a draft at PAUSE and red CI at RULING ESCALATES."""
        cases = {
            "a clean draft at RULING DUE": clean(DUE, draft=True),
            "a clean draft at PAUSE": clean(PAUSE, draft=True),
            "red CI at RULING ESCALATES": red(ESCALATES),
            "red CI at RULING DUE": red(DUE),
            "red CI at PAUSE": red(PAUSE),
        }
        shown = {
            label: (line in sweep(here).out, flows.listed_for_third(here))
            for label, (here, line) in cases.items()
        }
        assert_that(shown, equal_to({label: (True, []) for label in cases}))

"""A clean PR at a ruling keeps it: no review and no CI fix is offered (pitboss#183).

The draft gate and the CI gate of ``flow.next_step`` answer before the rejection
step, so a clean draft PR whose ruling is due or that is paused, and a clean PR
with red CI whose ruling escalates, must still get the rejection's step: its
decision is the ruling, the pause or the escalation, never a round.
"""

import unittest

from hamcrest import assert_that, equal_to

from . import fakes, test_flow_sweep as flows, world
from .test_commands import sweep
from .test_slot_commands import next_output

DUE = "ruling due after two plan rejections"
OWNER = "pause after a ruling and another rejection"
GIVEN_UP = "the ruling escalates"
ESCALATION = flows.EXECUTION_TWICE + [flows.ruled_by("Ruling: escalate to the owner")]
AFTER_RULING = flows.RULED + [flows.graded(flows.CHANGES, None, 4)]
ROUNDS = (flows.TWO_PLAN_REJECTIONS, AFTER_RULING, ESCALATION)
LINES = (flows.RULING_LINE, flows.PAUSE_LINE, flows.ESCALATES)
WAITING = dict(zip((DUE, OWNER, GIVEN_UP), zip(ROUNDS, LINES)))


def clean(name: str, **changes: object) -> tuple[world.World, str]:
    """A clean PR 3 at a wait.

    Args:
        name: the wait, a key of ``WAITING``.
        **changes: changes to PR 3's JSON (``draft``).

    Returns:
        The world, and the start of the wait's line.
    """
    rounds, line = WAITING[name]
    return flows.world_with(rounds, **changes), line


def red(name: str) -> tuple[world.World, str]:
    """A clean PR 3 at a wait, with red CI.

    Args:
        name: the wait, a key of ``WAITING``.

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
        """A draft whose ruling is due or that is paused, and red CI that escalates."""
        cases = {
            "a clean draft at the ruling": clean(DUE, draft=True),
            "a clean draft at the pause": clean(OWNER, draft=True),
            "red CI at the escalation": red(GIVEN_UP),
            "red CI at the ruling": red(DUE),
            "red CI at the pause": red(OWNER),
        }
        shown = {
            label: (
                line in sweep(here).out,
                line in "".join(flows.listed_for_third(here)),
                "fix CI on the head" in next_output(here),
            )
            for label, (here, line) in cases.items()
        }
        assert_that(shown, equal_to({label: (True, True, False) for label in cases}))

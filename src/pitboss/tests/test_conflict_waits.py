"""A dirty PR keeps its wait: a ruling or the owner comes before the conflict.

The Opus ruling on pitboss#181: ``flow.next_step`` returns a wait (``steps.UNRESOLVED``,
the paused-owner label and an unreadable ruling) before the conflict, and a
ruling's own work step after it. The sweep keeps the line of each wait next to
``CONFLICT``, and ``slots next`` lists nothing for it.
"""

from hamcrest import assert_that, contains_string, equal_to

from . import test_flow_sweep as flows, world
from .test_commands import sweep

DIRTY = flows.DIRTY
ESCALATES = "RULING ESCALATES owner/project#3"
WAITING = {
    "ruling due after two plan rejections": (
        flows.TWO_PLAN_REJECTIONS,
        flows.RULING_LINE,
    ),
    "ruling due after the execution is rejected twice": (
        flows.EXECUTION_TWICE,
        flows.RULING_LINE,
    ),
    "pause after a ruling and another rejection": (
        [*flows.RULED, flows.graded(flows.CHANGES, None, 4)],
        flows.PAUSE_LINE,
    ),
    "the ruling escalates": (
        [*flows.TWO_PLAN_REJECTIONS, flows.ruled_by("Ruling: escalate to the owner")],
        ESCALATES,
    ),
}


def assert_waits(here: world.World, line: str) -> None:
    """Assert the sweep prints the wait and CONFLICT, and nothing is listed.

    Args:
        here: the world.
        line: the start of the wait's line.
    """
    swept = sweep(here).out
    assert_that(swept, contains_string(line))
    assert_that(swept, contains_string("CONFLICT owner/project#3"))
    assert_that(flows.listed_for_third(here), equal_to([]))

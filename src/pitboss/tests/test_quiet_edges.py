"""The quiet period at its edges: sweep, a failed record write, minutes."""

import unittest

from hamcrest import assert_that, equal_to

from . import test_quiet as helpers
from . import world


def configure_runners(here: world.World, text: str) -> None:
    """Add a ``[runners]`` table to a world's configuration.

    Args:
        here: the world.
        text: the table's lines.
    """
    with open(here.config, "a", encoding="utf-8") as stream:
        stream.write(f"\n[runners]\n{text}\n")


def pressure_line(here: world.World) -> str:
    """The pressure line a sweep of a world prints at minute 0.

    Args:
        here: the world.

    Returns:
        The line.
    """
    out = world.again(here, "sweep", "--now", helpers.at(0)).out
    return [x for x in out.splitlines() if "RUNNER PRESSURE" in x][0]


class TestSweep(unittest.TestCase):
    """``sweep`` reads the record and writes nothing."""

    def test_sweep_line_follows_the_record(self) -> None:
        """Quiet, in the quiet period and under pressure: the line each time."""
        worlds = [helpers.clear_world(), helpers.clear_world(), world.make_world()]
        helpers.write(worlds[0], helpers.hold_at(-60))
        helpers.write(worlds[1], helpers.hold_at(-5))
        found = list(map(pressure_line, worlds))
        written = list(map(helpers.lines, worlds))
        wanted = [
            helpers.CLEAR,
            helpers.QUIET.replace("15 quiet", "10 quiet"),
            helpers.WAITING,
        ]
        assert_that(found, equal_to(wanted))
        seeds = [helpers.hold_at(minute).strip() for minute in (-60, -5)]
        kept = [[seeds[0]], [seeds[1]], []]
        assert_that(written, equal_to(kept))


class TestEdges(unittest.TestCase):
    """A failed record write, and minutes against jobs."""

    def test_push_went_out_but_the_hold_was_not_recorded(self) -> None:
        """It says the push went out, tells what to run, and exits 2."""
        here = helpers.clear_world()
        missing = here.workspace / "missing" / "log"
        configure_runners(here, f"quiet_minutes = 0\nrecord = '{missing}'")
        result = world.again(here, "push", "--now", helpers.at(0), "--no-dry-run")
        said = ("push WENT OUT" in result.out, "run `pitboss queued`" in result.out)
        assert_that(
            (result.code, helpers.pushes(here), said), equal_to((2, 1, (True, True)))
        )

    def test_zero_quiet_minutes_with_jobs_waiting(self) -> None:
        """Three jobs waiting and no quiet period: exit 1, 0 minutes remain."""
        here = world.make_world(helpers.GIT_ANSWERS)
        here.bodies[helpers.PROJECT_JOBS] = {"jobs": [{"status": "queued"}] * 3}
        configure_runners(here, "quiet_minutes = 0")
        result = world.again(here, "pressure", "--now", helpers.at(0))
        line = result.out.splitlines()[-1]
        head = "RUNNER PRESSURE: 3 queue-run jobs waiting for a runner"
        wanted = f"{head}: {helpers.HOLD}; 0 quiet minutes remain"
        assert_that((result.code, line), equal_to((1, wanted)))

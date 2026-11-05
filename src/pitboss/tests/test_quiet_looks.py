"""Every look is recorded, the first one starts the clock (pitboss#215)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import report
from . import test_quiet as helpers
from . import fakes, quietworld, world


def refused_push(here: world.World, minute: int) -> world.Result:
    """Run a push at a minute, as a worker would.

    Args:
        here: the world.
        minute: minutes after the start.

    Returns:
        What it did.
    """
    return world.again(
        here, "push", "--now", helpers.at(minute), "--no-dry-run", "origin"
    )


class TestRecordedLooks(unittest.TestCase):
    """A refused push, a sweep and a next write the look they made."""

    def test_refused_push_records_its_look(self) -> None:
        """A push in the quiet period is refused; its none look does not restart it."""
        here = helpers.clear_world()
        helpers.exit_code(here, "queued", 0)
        result = refused_push(here, 10)
        found = (result.code, helpers.lines(here), helpers.pushes(here))
        wanted = (1, [f"{helpers.at(0)} hold", f"{helpers.at(10)} none"], 0)
        assert_that(found, equal_to(wanted))
        assert_that(helpers.exit_code(here, "pressure", 15), equal_to(0))

    def test_first_look_of_an_empty_record_starts_the_clock(self) -> None:
        """With no record a refused push says the quiet period starts now."""
        here = helpers.clear_world()
        first = refused_push(here, 0)
        found = (first.code, helpers.FIRST_LOOK in first.out, helpers.lines(here))
        assert_that(found, equal_to((1, True, [f"{helpers.at(0)} none"])))
        later = refused_push(here, 15)
        assert_that((later.code, helpers.pushes(here)), equal_to((0, 1)))

    def test_refused_push_under_pressure_records_a_hold(self) -> None:
        """A refused push that saw a job waiting records a hold."""
        here = helpers.waiting_world(1)
        found = (refused_push(here, 0).code, helpers.lines(here))
        assert_that(found, equal_to((1, [f"{helpers.at(0)} hold"])))

    def test_sweep_and_next_end_the_quiet_period(self) -> None:
        """A sweep or a next on a new record writes a none look, and the clock runs.

        ``sweep`` prints the line that says the quiet period starts now, with a
        draft PR open too (its undraft check writes the first look); ``next``
        prints no pressure line at all.
        """
        for command, draft in (("sweep", False), ("sweep", True), ("next", False)):
            here = helpers.clear_world()
            if draft:
                here.bodies[f"{world.PROJECT}/pulls/3"] = fakes.pull_body(3, draft=True)
            first = world.again(here, command, "--now", helpers.at(0))
            said = (helpers.FIRST_LOOK in first.out, "PRESSURE" in first.out)
            assert_that(said, equal_to((command == "sweep",) * 2))
            assert_that(helpers.lines(here), equal_to([f"{helpers.at(0)} none"]))
            assert_that(helpers.exit_code(here, "pressure", 15), equal_to(0))


class TestNoRunnersTable(unittest.TestCase):
    """A configuration with no ``[runners]`` table never holds."""

    def test_nothing_is_held_or_recorded(self) -> None:
        """Sweep, next, pressure, queued and push say no hold and write nothing."""
        here = helpers.clear_world()
        quietworld.edit_config(here, "[runners]\n", "")
        said = [
            world.again(here, command, "--now", helpers.at(0))
            for command in ("sweep", "next", "pressure", "queued")
        ]
        pushed = refused_push(here, 0)
        holds = [report.no_hold_line() in said[each].out for each in (0, 2)]
        found = (holds, pushed.code, helpers.pushes(here), helpers.lines(here))
        assert_that(found, equal_to(([True] * 2, 0, 1, [])))
        assert_that(said[3].out, contains_string("nothing recorded"))

"""The sweep's OUTDATED line: the running pitboss against PyPI's newest (#103)."""

import json
import unittest

import pitboss
from hamcrest import assert_that, equal_to

from .. import outdated
from . import test_commands, world

INDEX = "https://pypi.org/pypi/pitboss/json"
RUNNING = "2026.10.28.62127.dev1"
NEWEST = "2026.10.30.50353"
LINE = f"OUTDATED pitboss {RUNNING} < {NEWEST}"


def answer(version: str) -> str:
    """What PyPI's JSON API answers for a newest release.

    Args:
        version: the release.

    Returns:
        The body.
    """
    return json.dumps({"info": {"version": version}})


def sweep_with(index: object) -> world.Result:
    """Sweep a world whose PyPI answers a body, or fails when there is none.

    Args:
        index: PyPI's answer, None for a failed call.

    Returns:
        What the sweep did.
    """
    here = world.make_world()
    here.bodies[test_commands.OPEN_PULLS] = [{"number": 2}]
    if index is not None:
        here.bodies[INDEX] = index
    return test_commands.sweep(here)


class TestLines(unittest.TestCase):
    """The line, from the running and the newest version."""

    def test_older_than_pypi(self) -> None:
        """A running version below PyPI's newest prints the one line."""
        assert_that(outdated.lines(RUNNING, NEWEST), equal_to([LINE]))

    def test_current(self) -> None:
        """The newest release itself prints nothing."""
        assert_that(outdated.lines(NEWEST, NEWEST), equal_to([]))

    def test_unreadable_pypi(self) -> None:
        """A PyPI that could not be read prints nothing."""
        assert_that(outdated.lines(RUNNING, None), equal_to([]))

    def test_ahead_of_pypi(self) -> None:
        """A running version above PyPI's newest prints nothing."""
        assert_that(outdated.lines(NEWEST, RUNNING), equal_to([]))

    def test_dev_build_of_the_newest(self) -> None:
        """A dev build of the newest release is older than the release."""
        line = f"OUTDATED pitboss {NEWEST}.dev1 < {NEWEST}"
        assert_that(outdated.lines(f"{NEWEST}.dev1", NEWEST), equal_to([line]))

    def test_pre_releases_of_ci_builds(self) -> None:
        """Every pre-release form autocalver gives is older than its release (#103)."""
        found = [
            outdated.lines(f"{NEWEST}{suffix}", NEWEST)
            for suffix in ("rc1", ".dev1", "a1", "b2")
        ]
        expected = [
            [f"OUTDATED pitboss {NEWEST}{each} < {NEWEST}"]
            for each in ("rc1", ".dev1", "a1", "b2")
        ]
        assert_that(found, equal_to(expected))

    def test_versions_that_are_not_dates(self) -> None:
        """A version this does not understand is never reported."""
        assert_that(outdated.lines("local", NEWEST), equal_to([]))


class TestNewest(unittest.TestCase):
    """Reading PyPI through the runner."""

    def test_reads_the_version(self) -> None:
        """The newest release is PyPI's ``info.version``."""
        here = world.make_world()
        here.bodies[INDEX] = answer(NEWEST)
        assert_that(outdated.newest(here.processes), equal_to(NEWEST))

    def test_failed_call(self) -> None:
        """A call that fails is None."""
        assert_that(outdated.newest(world.make_world().processes), equal_to(None))

    def test_bad_answers(self) -> None:
        """An answer that is not PyPI's shape is None."""
        found = []
        for body in ("not json", "[]", "{}", json.dumps({"info": {"version": 3}})):
            here = world.make_world()
            here.bodies[INDEX] = body
            found.append(outdated.newest(here.processes))
        assert_that(found, equal_to([None] * 4))

    def test_no_curl(self) -> None:
        """A machine without curl is None."""
        here = world.make_world(answers={"curl": 127})
        assert_that(outdated.newest(here.processes), equal_to(None))


class TestSweep(unittest.TestCase):
    """The sweep prints the line first, in the three cases of the ticket."""

    def test_outdated(self) -> None:
        """A newer release on PyPI gives the line, before the PR lines."""
        result = sweep_with(answer("9999.1.1"))
        expected = f"OUTDATED pitboss {pitboss.__version__} < 9999.1.1"
        assert_that(result.out.splitlines()[0], equal_to(expected))

    def test_current(self) -> None:
        """The running release being the newest gives no line."""
        result = sweep_with(answer(pitboss.__version__))
        assert_that("OUTDATED" in result.out, equal_to(False))

    def test_unreadable(self) -> None:
        """A PyPI that cannot be read gives no line, and the sweep goes on."""
        result = sweep_with(None)
        found = ("OUTDATED" in result.out, "READY TO MERGE" in result.out)
        assert_that(found, equal_to((False, True)))

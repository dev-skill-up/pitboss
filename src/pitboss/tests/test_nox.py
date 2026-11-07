"""Tests for ``pitboss nox``, the worker's local check (pitboss#210)."""

import dataclasses
import unittest
from typing import Mapping, MutableSequence, Sequence

from hamcrest import assert_that, equal_to

from .. import expansion, noxcheck
from . import world
from .briefmake import has_all, has_none

COMMANDS = [
    ["nox", "-r", "-s", "skills"],
    ["nox", "-r", "-s", "lint"],
    ["nox", "-r", "-s", "mypy"],
    ["nox", "-r", "-s", "tests-3.13", "--", "-x"],
]
SUCCESS_LINES = [
    ["skills", "success"],
    ["lint", "success"],
    ["mypy", "success"],
    ["tests-3.13", "success"],
]
MODULES = ["pitboss.tests.test_gates", "pitboss.tests.test_nox"]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Done:
    """A finished fake process.

    Attributes:
        returncode: its exit status.
        stdout: its output.
    """

    returncode: int
    stdout: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FakeNox:
    """Answers every ``nox`` command line from canned statuses, running no nox.

    Attributes:
        statuses: the exit status of each session by name; 0 when absent.
        calls: every command line run, in order.
    """

    statuses: Mapping[str, int]
    calls: MutableSequence[Sequence[str]]

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> Done:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: ignored (what gather passes to ``subprocess.run``).

        Returns:
            The finished process, which printed its session's name.
        """
        self.calls.append(list(cmdargs))
        name = cmdargs[3]
        timing = f"{noxcheck.TIMING_PREFIX}total 1.000s in 1 tests\n"
        shown = timing if name == "tests-3.13" else ""
        return Done(
            returncode=self.statuses.get(name, 0),
            stdout=f"output of {name}\n{shown}",
        )


def run_nox(
    statuses: Mapping[str, int], *options: str
) -> tuple[world.Result, Sequence[Sequence[str]]]:
    """Run ``pitboss nox`` with a fake nox.

    Args:
        statuses: the exit status of each session by name; 0 when absent.
        *options: the words after ``nox``.

    Returns:
        What the command did, and the command lines it ran.
    """
    fake = FakeNox(statuses=statuses, calls=[])
    here = dataclasses.replace(
        world.make_world(),
        processes=fake,  # type: ignore[arg-type]
    )
    return world.invoke(here, "nox", *options), fake.calls


def clock_of(*readings: float) -> noxcheck.Clock:
    """A clock that reads the given seconds, one for each call.

    Args:
        *readings: the seconds, in order.

    Returns:
        The clock.
    """
    found = iter(readings)
    return lambda: next(found)


class TestNoxCommand(unittest.TestCase):
    """``pitboss nox`` runs four sessions in order, each with ``-r``."""

    def test_it_runs_the_four_sessions_in_order_with_r(self) -> None:
        """skills, lint and mypy first, tests-3.13 last; never without -r."""
        found, calls = run_nox({})
        assert_that(calls, equal_to(COMMANDS))
        assert_that(found.code, equal_to(0))

    def test_it_prints_a_line_for_each_session_and_names_the_proof(self) -> None:
        """Name, success, seconds; then CI's `Run Nox` step is the proof."""
        found, _ = run_nox({})
        shown = found.out.splitlines()
        lines = [line for line in shown if not line.startswith(noxcheck.TIMING_PREFIX)]
        assert_that([line.split()[0:2] for line in lines[:4]], equal_to(SUCCESS_LINES))
        assert_that(shown[0].endswith("s"), equal_to(True))
        assert_that(lines[4:], equal_to([noxcheck.PROOF]))

    def test_a_passing_run_shows_the_timing_after_the_tests_line(self) -> None:
        """The captured output is not shown on success, the timing lines are."""
        found, _ = run_nox({})
        shown = found.out.splitlines()
        timing = f"{noxcheck.TIMING_PREFIX}total 1.000s in 1 tests"
        assert_that(shown[4], equal_to(timing))
        assert_that(shown[3].startswith("tests-3.13 success"), equal_to(True))
        has_none(found.out, ["output of tests-3.13"])

    def test_a_failed_tests_session_shows_the_timing_once(self) -> None:
        """Its whole output is shown, and the timing is not printed twice."""
        found, _ = run_nox({"tests-3.13": 1})
        timing = f"{noxcheck.TIMING_PREFIX}total 1.000s in 1 tests"
        assert_that(found.out.count(timing), equal_to(1))
        has_all(found.out, ["tests-3.13 failed", "output of tests-3.13"])

    def test_it_stops_at_the_first_failure(self) -> None:
        """Whichever session fails, none after it runs, and the exit is 1."""
        for index, command in enumerate(COMMANDS):
            found, calls = run_nox({command[3]: 2})
            assert_that((calls, found.code), equal_to((COMMANDS[: index + 1], 1)))

    def test_the_failed_session_shows_its_output_and_no_other(self) -> None:
        """lint fails: its output, no passing session's, and no proof."""
        found, _ = run_nox({"lint": 1})
        has_all(found.out, ["lint failed", "output of lint\n"])
        has_none(found.out, ["output of skills", "mypy", noxcheck.PROOF])

    def test_module_names_go_to_the_tests_session_only(self) -> None:
        """Words after `--` are the tests session's posargs."""
        _, calls = run_nox({}, *MODULES)
        expected = [*COMMANDS[:3], [*COMMANDS[3], *MODULES]]
        assert_that(calls, equal_to(expected))

    def test_the_tests_command_carries_the_stop_after_option(self) -> None:
        """-x is in the tests command whatever the arguments, and in no other."""
        for words in ([], MODULES, ["pitboss.tests.test_gates"]):
            _, calls = run_nox({}, *words)
            assert_that(calls[-1][4:6], equal_to(["--", "-x"]))
            assert_that([each for each in calls[:3] if "-x" in each], equal_to([]))

    def test_a_cheap_session_that_fails_keeps_the_tests_from_running(self) -> None:
        """Red in mypy: the 4-minute tests never start."""
        found, calls = run_nox({"mypy": 1})
        assert_that(calls, equal_to(COMMANDS[:3]))
        has_none(found.out, ["tests-3.13", noxcheck.PROOF])


class TestNoxSessions(unittest.TestCase):
    """The sessions, in order, with the seconds each took."""

    def test_the_lines_are_the_names_the_results_and_the_clocks_seconds(self) -> None:
        """Each line has the session, success, and the seconds it took."""
        readings = clock_of(0, 7, 7, 18, 18, 33, 33, 52)
        done = expansion.Outcome(status=0, output="")
        ran = noxcheck.run_sessions(lambda _: done, readings, [])
        shown = [noxcheck.line_of(each) for each in ran]
        assert_that(
            shown,
            equal_to(
                [
                    "skills success 7s",
                    "lint success 11s",
                    "mypy success 15s",
                    "tests-3.13 success 19s",
                ]
            ),
        )

    def test_a_failed_session_says_failed_and_ends_the_list(self) -> None:
        """Only the sessions up to the failed one."""
        bad = expansion.Outcome(status=1, output="")
        ran = noxcheck.run_sessions(lambda _: bad, clock_of(0, 2), [])
        shown = [noxcheck.line_of(each) for each in ran]
        assert_that(shown, equal_to(["skills failed 2s"]))

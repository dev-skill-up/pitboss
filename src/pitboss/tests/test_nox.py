"""Tests for ``pitboss nox``, the worker's local check (pitboss#210)."""

import dataclasses
import os
import pathlib
import re
import unittest
from typing import Callable, Mapping, MutableSequence, Sequence

from hamcrest import assert_that, equal_to

from .. import disk, diskwatch, expansion, noxcheck, noxenv
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
SELECTION = "test-selection"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Done:
    """A finished fake process.

    Attributes:
        returncode: its exit status.
        stdout: its output.
    """

    returncode: int
    stdout: str


def cannot_say(cmdargs: Sequence[str]) -> Done:
    """Answer git, asked for the diff: it cannot say, so every test is run.

    Args:
        cmdargs: the command line.

    Returns:
        A failed process.
    """
    return Done(returncode=1, stdout=" ".join(cmdargs[:2]))


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FakeNox:
    """Answers every ``nox`` command line from canned statuses, running no nox.

    Attributes:
        statuses: the exit status of each session by name; 0 when absent.
        calls: every ``nox`` command line run, in order.
        git: answers the command lines that are not ``nox``.
        environments: the ``env`` each ``nox`` command line was given (none when
            it was given no environment), in order.
    """

    statuses: Mapping[str, int]
    calls: MutableSequence[Sequence[str]]
    git: Callable[[Sequence[str]], Done] = cannot_say
    environments: MutableSequence[object] = dataclasses.field(default_factory=list)

    def __call__(self, cmdargs: Sequence[str], /, **kwargs: object) -> Done:
        """Run a command.

        Args:
            cmdargs: the command line.
            **kwargs: what gather passes to ``subprocess.run``, of which ``env``
                is kept for a ``nox`` command line.

        Returns:
            The finished process, which printed its session's name.
        """
        if cmdargs[0] != "nox":
            return self.git(cmdargs)
        self.calls.append(list(cmdargs))
        self.environments.append(kwargs.get("env"))
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
    return run_with(fake, *options), fake.calls


def run_with(processes: object, *options: str) -> world.Result:
    """Run ``pitboss nox`` in a world whose processes are given.

    Args:
        processes: what runs the command lines (git and nox).
        *options: the words after ``nox``.

    Returns:
        What the command did.
    """
    here = dataclasses.replace(
        world.make_world(),
        processes=processes,  # type: ignore[arg-type]
    )
    return world.invoke(here, "nox", *options)


def without_selection(output: str) -> Sequence[str]:
    """The lines of an output that are not about the test selection.

    Args:
        output: what the command printed.

    Returns:
        Its lines, those that start with ``test-selection`` left out.
    """
    return [each for each in output.splitlines() if not each.startswith(SELECTION)]


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

    def test_it_names_the_proof_and_ends_with_a_line_for_each_session(self) -> None:
        """The proof, then name, success and seconds of each: the last lines."""
        found, _ = run_nox({})
        shown = without_selection(found.out)
        lines = [line for line in shown if not line.startswith(noxcheck.TIMING_PREFIX)]
        assert_that(lines[0], equal_to(noxcheck.PROOF))
        assert_that([line.split()[0:2] for line in lines[1:]], equal_to(SUCCESS_LINES))

    def test_a_passing_run_shows_the_timing_before_the_summary(self) -> None:
        """The captured output is not shown on success, the timing lines are."""
        found, _ = run_nox({})
        shown = without_selection(found.out)
        timing = f"{noxcheck.TIMING_PREFIX}total 1.000s in 1 tests"
        assert_that(shown[:2], equal_to([timing, noxcheck.PROOF]))
        has_none(found.out, ["output of tests-3.13"])

    def test_a_failed_tests_session_shows_the_timing_once(self) -> None:
        """Its whole output is shown, and the timing is not printed twice."""
        found, _ = run_nox({"tests-3.13": 1})
        timing = f"{noxcheck.TIMING_PREFIX}total 1.000s in 1 tests"
        assert_that(found.out.count(timing), equal_to(1))
        assert_that("output of tests-3.13" in found.out, equal_to(True))

    def test_it_stops_at_the_first_failure(self) -> None:
        """Whichever session fails, none after it runs, and the exit is 1."""
        for index, command in enumerate(COMMANDS):
            found, calls = run_nox({command[3]: 2})
            assert_that((calls, found.code), equal_to((COMMANDS[: index + 1], 1)))

    def test_the_failed_session_shows_its_output_and_no_other(self) -> None:
        """lint fails: its output, no passing session's, and no proof."""
        found, _ = run_nox({"lint": 1})
        has_all(found.out, ["lint failed", "output of lint\n"])
        has_none(found.out, ["output of skills", "output of mypy", noxcheck.PROOF])

    def test_the_tests_command_carries_the_stop_after_option(self) -> None:
        """-x is in the tests command whatever the arguments, and in no other."""
        for words in ([], ["--also", "pitboss.tests.test_gates=it reads a file"]):
            _, calls = run_nox({}, *words)
            assert_that(calls[-1][4:6], equal_to(["--", "-x"]))
            assert_that([each for each in calls[:3] if "-x" in each], equal_to([]))

    def test_a_cheap_session_that_fails_keeps_the_tests_from_running(self) -> None:
        """Red in mypy: the 4-minute tests never start."""
        found, calls = run_nox({"mypy": 1})
        assert_that(calls, equal_to(COMMANDS[:3]))
        has_none(found.out, ["output of tests-3.13", noxcheck.PROOF])


GIBIBYTE = 2**30
CLEAN = "uvx pitboss clean-container --no-dry-run"


def usage_with(free: int) -> disk.Usage:
    """The use of a 100 GiB volume with some bytes free.

    Args:
        free: the bytes free.

    Returns:
        The use.
    """
    return disk.Usage(100 * GIBIBYTE, 100 * GIBIBYTE - free, free)


def run_on_disk(
    reader: disk.Reader,
) -> tuple[world.World, world.Result, Sequence[Sequence[str]]]:
    """Run ``pitboss nox`` with a fake nox on a volume whose use is given.

    Args:
        reader: reads the use of the working directory's volume.

    Returns:
        The world, what the command did, and the ``nox`` command lines it ran.
    """
    fake = FakeNox(statuses={}, calls=[])
    here = dataclasses.replace(
        world.make_world(),
        processes=fake,  # type: ignore[arg-type]
        usage=reader,
    )
    return here, world.invoke(here, "nox"), fake.calls


class TestNoxChecksTheDisk(unittest.TestCase):
    """Under 5 GiB free it stops before a session, with the line and the clean."""

    def test_under_five_gibibytes_it_exits_1_with_the_disk_line_and_the_clean(
        self,
    ) -> None:
        """The `next` line (one source), then the auto-approved command; no nox."""
        usage = usage_with(5 * GIBIBYTE - 1)
        here, found, calls = run_on_disk(lambda _: usage)
        shown = diskwatch.line(diskwatch.Reading(place=here.workspace, usage=usage))
        assert_that((found.code, calls), equal_to((1, [])))
        assert_that(found.out.splitlines()[0], equal_to(shown))
        has_all(found.out, ["DISK ", CLEAN, "under 5.0 GiB free"])
        has_none(found.out, ["test-selection", "success"])

    def test_the_refusal_names_the_volume_it_read_and_its_free_space(self) -> None:
        """4 GiB free of 100: the figures of the line are the volume's."""
        _, found, _ = run_on_disk(lambda _: usage_with(4 * GIBIBYTE))
        has_all(found.out, ["4.0 GiB free of 100.0 GiB (96.0% used)"])

    def test_at_five_gibibytes_or_with_no_figure_it_runs_the_four_sessions(
        self,
    ) -> None:
        """Exactly the limit is enough (the nearest input); no figure, no refusal."""
        readers: Sequence[disk.Reader] = (
            lambda _: usage_with(5 * GIBIBYTE),
            lambda _: None,
        )
        for usage_of in readers:
            _, found, calls = run_on_disk(usage_of)
            assert_that((found.code, calls), equal_to((0, COMMANDS)))
            has_none(found.out, [CLEAN, "DISK "])


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


NAMES = [each.value for each in noxcheck.Session]
SECONDS = re.compile(r" \d+s$")
SUMMARIES = {
    "": ["skills success", "lint success", "mypy success", "tests-3.13 success"],
    "skills": ["skills failed", "lint not run", "mypy not run", "tests-3.13 not run"],
    "lint": ["skills success", "lint failed", "mypy not run", "tests-3.13 not run"],
    "mypy": ["skills success", "lint success", "mypy failed", "tests-3.13 not run"],
    "tests-3.13": [
        "skills success",
        "lint success",
        "mypy success",
        "tests-3.13 failed",
    ],
}


def summary_of(output: str) -> Sequence[str]:
    """The last four lines of an output, without their seconds.

    Args:
        output: what the command printed.

    Returns:
        The lines: a session's name and `success`, `failed` or `not run`.
    """
    return [SECONDS.sub("", each) for each in output.splitlines()[-len(NAMES) :]]


class TestNoxSummary(unittest.TestCase):
    """The last lines are one for each session, in the order they run."""

    def test_each_run_ends_with_the_status_of_every_session(self) -> None:
        """Success, failed for the one that failed, not run for the rest."""
        for failing, expected in SUMMARIES.items():
            with self.subTest(failing):
                found, _ = run_nox({failing: 1} if failing else {})
                assert_that(summary_of(found.out), equal_to(expected))
                assert_that(found.code, equal_to(1 if failing else 0))

    def test_the_summary_of_sessions_that_ran_is_followed_by_not_run(self) -> None:
        """Two ran: their lines with the seconds, then `not run` for the others."""
        done = expansion.Outcome(status=0, output="")
        two = noxcheck.WITHOUT_TESTS[:2]
        ran = noxcheck.run_sessions(lambda _: done, clock_of(0, 7, 7, 8), [], two)
        expected = ["skills success 7s", "lint success 1s"]
        expected += ["mypy not run", "tests-3.13 not run"]
        assert_that(noxcheck.summary_of(ran), equal_to(expected))


class TestLintFailure(unittest.TestCase):
    """A lint failure names the command to repeat alone (pitboss#364)."""

    def test_lint_red_starts_no_test_and_names_the_lint_only_rerun(self) -> None:
        """The tests session never starts; the command line that ran is printed."""
        found, calls = run_nox({"lint": 1})
        rerun = noxcheck.LINT_RERUN.format(command=" ".join(calls[1]))
        assert_that(calls, equal_to(COMMANDS[:2]))
        has_all(found.out, [rerun, "output of lint", "nox -r -s lint"])
        has_none(found.out, ["output of tests-3.13"])

    def test_no_other_session_failing_names_a_rerun(self) -> None:
        """The nearest input: only lint has one, and a passing lint prints none."""
        for name in ("skills", "mypy", "tests-3.13"):
            with self.subTest(name):
                found, _ = run_nox({name: 1})
                has_none(found.out, ["lint-rerun"])


def snapshot() -> tuple[Mapping[str, str], bytes]:
    """This process's environment and the text of ``~/.gitconfig``.

    Returns:
        Both; the text is empty when the file is not there.
    """
    gitconfig = pathlib.Path.home() / ".gitconfig"
    text = gitconfig.read_bytes() if gitconfig.exists() else b""
    return dict(os.environ), text


class TestNoxHome(unittest.TestCase):
    """The sessions run with a throwaway HOME and no git identity (pitboss#364)."""

    def test_each_session_gets_the_isolated_environment_of_one_home(self) -> None:
        """One HOME, gone after the run; a git config inside it; no identity."""
        before = snapshot()
        fake = FakeNox(statuses={}, calls=[])
        run_with(fake)
        environments = [each for each in fake.environments if isinstance(each, Mapping)]
        homes = {each["HOME"] for each in environments}
        configs = [
            each["GIT_CONFIG_GLOBAL"].startswith(each["HOME"]) for each in environments
        ]
        identity = [
            key for each in environments for key in noxenv.IDENTITY if key in each
        ]
        assert_that((len(environments), len(homes)), equal_to((4, 1)))
        assert_that((configs, identity), equal_to(([True] * 4, [])))
        assert_that(
            (os.path.exists(homes.pop()), snapshot()), equal_to((False, before))
        )

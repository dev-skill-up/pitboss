"""Tests for what ``pitboss nox`` prints last and the environment it gives (#364)."""

import os
import pathlib
import re
import unittest
from collections.abc import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import expansion, noxcheck, noxenv
from .says import has_all, has_none
from .test_nox import COMMANDS, Done, FakeNox, clock_of, run_nox, run_with

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
        has_all(
            found.out, [rerun, "output of lint", "nox -r -s lint", "`nox -s lint -r`"]
        )
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


SKIPPED_LINE = "nox > Session skills skipped: Python interpreter 3.14 not found.\n"


def skipping_nox(cmdargs: Sequence[str], /, **kwargs: object) -> Done:
    """A nox whose every session is skipped for want of Python 3.14.

    Args:
        cmdargs: the command line.
        **kwargs: what gather passes to ``subprocess.run``.

    Returns:
        Exit 0 with nox's skip line.
    """
    return Done(returncode=0, stdout=SKIPPED_LINE)


class TestNoxSkipped(unittest.TestCase):
    """A session nox skipped for a missing interpreter is a failure (pitboss#426)."""

    def test_a_skipped_session_fails_naming_the_interpreter_and_its_install(
        self,
    ) -> None:
        """Exit 0 from nox, but the line says skipped: failed, stops, exits 1."""
        calls: list[Sequence[str]] = []

        def runner(command: Sequence[str], /) -> expansion.Outcome:
            calls.append(command)
            return expansion.Outcome(status=0, output=SKIPPED_LINE)

        ran = noxcheck.run_sessions(runner, clock_of(*range(8)), [])
        first = noxcheck.summary_of(ran)[0]
        assert_that([len(calls), first], equal_to([1, "skills failed 1s"]))
        has_all(ran[0].outcome.output, ["Python 3.14", "`uv python install 3.14`"])

    def test_the_command_shows_the_failure_and_not_success(self) -> None:
        """Through the whole command: the exit is 1 and no line says success."""
        found = run_with(skipping_nox)
        has_none(found.out, ["skills success", "lint success"])
        words = ["skills failed", "uv python install 3.14"]
        self.assertEqual([word in found.out for word in words], [True, True])
        self.assertEqual((found.code, found.out.count("skills failed")), (1, 1))

    def test_a_session_that_ran_and_mentions_skipped_tests_still_passes(self) -> None:
        """The nearest input: other `skipped` text is not a missing interpreter."""
        output = "3 tests skipped: not found\n"
        done = expansion.Outcome(status=0, output=output)
        judged = noxcheck.judged(done)
        self.assertEqual((judged.status, judged.output), (0, output))

"""The tests session of noxfile.py: a targeted run has no 100% report (pitboss#210)."""

import contextlib
import dataclasses
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from collections.abc import Iterator, Mapping, Sequence
from typing import Protocol

from hamcrest import assert_that, equal_to

from .. import noxcheck
from .briefmake import has_all, has_none
from .test_config import EXAMPLE
from .fakes import write


@contextlib.contextmanager
def nox_stand_in() -> Iterator[None]:
    """Put a stand-in for the ``nox`` module where noxfile.py imports it from.

    Yields:
        Nothing, while the stand-in is the module.
    """
    stand_in = types.ModuleType("nox")
    stand_in.options = types.SimpleNamespace()  # type: ignore[attr-defined]
    stand_in.session = lambda **_: lambda each: each  # type: ignore[attr-defined]
    # the tests environment does not install nox, so there is none to put back
    sys.modules["nox"] = stand_in
    try:
        yield
    finally:
        del sys.modules["nox"]


def commands_of(*posargs: str) -> Sequence[str]:
    """The programs the tests session runs, with nox playing no part.

    Args:
        *posargs: the words after ``--``.

    Returns:
        The program and its subcommand of each run.
    """
    return [" ".join(each[:2]) for each in runs_of(*posargs)]


REPORTER = "--reporter=pitboss.tests.timingreport.TimingReporter"


def virtue_words_of(*posargs: str) -> Sequence[str]:
    """The words after ``virtue`` in the run of the tests.

    Args:
        *posargs: the words after ``--``.

    Returns:
        What virtue is given: its options, then the modules.
    """
    first = runs_of(*posargs)[0]
    return list(first[first.index("virtue") + 1 :])


def runs_of(*posargs: str) -> Sequence[Sequence[str]]:
    """The commands the tests session runs, with nox playing no part.

    Args:
        *posargs: the words after ``--``.

    Returns:
        Each command, whole.
    """
    ran: list[Sequence[str]] = []
    with tempfile.TemporaryDirectory() as name:
        session = types.SimpleNamespace(
            posargs=posargs,
            create_tmp=lambda: made_tmp(pathlib.Path(name)),
            install=lambda *_: None,
            run=lambda *command, **_: ran.append(command),
        )
        noxfile_module().tests(session)
    return ran


def made_tmp(root: pathlib.Path) -> str:
    """The ``TMPDIR`` of a session, as nox makes it: ``tmp`` in the environment.

    Args:
        root: a directory to hold the environment.

    Returns:
        The path of the ``tmp`` directory, which exists.
    """
    tmp = root / "tests-3-13" / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return str(tmp)


def noxfile_module() -> types.ModuleType:
    """Load noxfile.py with a stand-in for nox.

    Returns:
        The module.
    """
    path = EXAMPLE.parents[1] / "noxfile.py"
    with nox_stand_in():
        spec = importlib.util.spec_from_file_location("noxfile_under_test", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class RunFailed(Exception):
    """The stand-in for a command of the session that exits with a status."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Left:
    """What a run of the tests session left of the things the tests made.

    Attributes:
        names: what is in ``TMPDIR`` afterwards, sorted.
        env: the environment the first command got (``COVERAGE_FILE`` and
            ``TMPDIR``).
        outside_kept: whether the directory a link in ``TMPDIR`` points at is
            still there.
    """

    names: Sequence[str]
    env: Mapping[str, str]
    outside_kept: bool


def things_left(root: pathlib.Path) -> pathlib.Path:
    """Make what tests leave in a ``TMPDIR``: a tree, a file and a link.

    Args:
        root: a directory to hold the environment.

    Returns:
        The directory the link points at.
    """
    tmp = pathlib.Path(made_tmp(root))
    (tmp / "world" / "project").mkdir(parents=True)
    write(tmp / "world" / "project" / "file", "x")
    write(tmp / "loose", "y")
    outside = root / "outside"
    outside.mkdir()
    (tmp / "link").symlink_to(outside)
    return outside


def left_after(*posargs: str, fails: bool = False) -> Left:
    """Run the tests session over a ``TMPDIR`` the tests left things in.

    Args:
        *posargs: the words after ``--``.
        fails: whether the run of the tests fails.

    Returns:
        What was left.
    """
    given: list[Mapping[str, str]] = []

    def run(*command: str, **kwargs: Mapping[str, str]) -> None:
        given.append(kwargs["env"])
        if fails and "virtue" in command:
            raise RunFailed()

    with tempfile.TemporaryDirectory() as top:
        root = pathlib.Path(top)
        outside = things_left(root)
        with contextlib.suppress(RunFailed):
            noxfile_module().tests(session_in(root, posargs, run))
        kept = sorted(each.name for each in (root / "tests-3-13" / "tmp").iterdir())
        return Left(names=kept, env=given[0], outside_kept=outside.is_dir())


class Run(Protocol):
    """What a command line of the session does."""

    def __call__(self, *command: str, **kwargs: Mapping[str, str]) -> None:
        """Run a command line.

        Args:
            *command: the words of the command.
            **kwargs: the options, of which ``env`` is read.
        """


def session_in(
    root: pathlib.Path, posargs: Sequence[str], run: Run
) -> types.SimpleNamespace:
    """A session whose environment is in a directory and whose commands are ``run``.

    Args:
        root: the directory.
        posargs: the words after ``--``.
        run: what a command line does.

    Returns:
        The session.
    """
    return types.SimpleNamespace(
        posargs=posargs,
        create_tmp=lambda: made_tmp(root),
        install=lambda *_: None,
        run=run,
    )


class TestTestsSession(unittest.TestCase):
    """The 100% report belongs to the whole run."""

    def test_the_whole_run_reports_coverage(self) -> None:
        """CI's run, with no module named, ends with the 100% report."""
        found = commands_of()
        assert_that(found[-1], equal_to("coverage report"))

    def test_a_targeted_run_has_no_coverage_report(self) -> None:
        """Named modules cover part of the package: no report to fail."""
        found = commands_of("pitboss.tests.test_gates")
        assert_that(found, equal_to(["coverage run"]))

    def test_a_stop_after_option_is_virtues_and_the_modules_stay_modules(self) -> None:
        """`-x` goes to virtue before the modules; the run is still targeted."""
        found = virtue_words_of("-x", "pitboss.tests.test_gates")
        assert_that(found, equal_to(["-x", REPORTER, "pitboss.tests.test_gates"]))
        targeted = commands_of("-x", "pitboss.tests.test_gates")
        assert_that(targeted, equal_to(["coverage run"]))

    def test_the_stop_after_option_alone_runs_every_test_and_the_report(self) -> None:
        """`pitboss nox` with no module: all the tests, stopping at a failure."""
        assert_that(virtue_words_of("-x"), equal_to(["-x", REPORTER, "pitboss.tests"]))
        assert_that(commands_of("-x")[-1], equal_to("coverage report"))

    def test_ci_runs_every_test_with_no_option(self) -> None:
        """CI's run passes nothing: no -x, so every test runs and is counted."""
        assert_that(virtue_words_of(), equal_to([REPORTER, "pitboss.tests"]))

    def test_the_timing_reporter_is_given_whatever_the_arguments(self) -> None:
        """No argument leaves the run without the timing (pitboss#324)."""
        for words in ([], ["-x"], ["-x", "pitboss.tests.test_gates"], ["-xx"]):
            assert_that(REPORTER in virtue_words_of(*words), equal_to(True))

    def test_an_argument_that_names_a_reporter_does_not_replace_the_timing(
        self,
    ) -> None:
        """The nearest input: `--reporter=text` is an option, and ours is after it."""
        found = virtue_words_of("--reporter=text")
        assert_that(found, equal_to(["--reporter=text", REPORTER, "pitboss.tests"]))
        assert_that(
            found.index(REPORTER) > found.index("--reporter=text"), equal_to(True)
        )


class TestTestsSessionEmptiesItsTmpdir(unittest.TestCase):
    """Only a green run removes what the tests left in TMPDIR (pitboss#346)."""

    def test_a_green_run_empties_it_whole_or_targeted(self) -> None:
        """The tree, the file and the link are gone; a link is not followed."""
        for words in ([], ["-x", "pitboss.tests.test_gates"]):
            found = left_after(*words)
            assert_that((found.names, found.outside_kept), equal_to(([], True)))

    def test_a_run_that_fails_keeps_it_for_debugging(self) -> None:
        """The nearest input: the tests fail and everything is still there."""
        found = left_after(fails=True)
        assert_that(found.names, equal_to(["link", "loose", "world"]))

    def test_the_coverage_data_is_beside_tmpdir_not_in_it(self) -> None:
        """Emptying TMPDIR leaves the data the 100% report reads."""
        env = left_after().env
        tmp, data = env["TMPDIR"], env["COVERAGE_FILE"]
        beside = os.path.join(os.path.dirname(tmp), "coverage")
        assert_that((data, data.startswith(tmp + os.sep)), equal_to((beside, False)))


FAILING_MODULE = """
import pathlib
import unittest

MARKER = pathlib.Path(__file__).with_name("later-test-ran")


class TestTwo(unittest.TestCase):
    def test_a_fails(self) -> None:
        self.fail("this one fails")

    def test_b_later(self) -> None:
        MARKER.write_text("ran")
"""


def run_virtue(root: pathlib.Path, *options: str) -> subprocess.CompletedProcess[str]:
    """Run the real virtue over the module of a failing test.

    Args:
        root: a directory to hold the module.
        *options: the options for virtue.

    Returns:
        The finished process, standard error joined to standard output.
    """
    write(root / "twotests.py", FAILING_MODULE)
    return subprocess.run(
        [sys.executable, "-m", "virtue", *options, "twotests"],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(root)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


class TestStopAfterOnAFailingTest(unittest.TestCase):
    """virtue's `-x` stops the run at the first failing test and reports it."""

    def test_a_failing_test_stops_the_run_and_is_reported(self) -> None:
        """With -x the test after the failing one never runs; the failure shows."""
        with tempfile.TemporaryDirectory() as name:
            root = pathlib.Path(name)
            done = run_virtue(root, "-x")
            later_ran = (root / "later-test-ran").exists()
        assert_that((done.returncode != 0, later_ran), equal_to((True, False)))
        has_all(done.stdout, ["this one fails", "test_a_fails"])

    def test_without_the_option_the_test_after_it_runs(self) -> None:
        """The nearest input: no -x, and the later test runs (CI's run)."""
        with tempfile.TemporaryDirectory() as name:
            root = pathlib.Path(name)
            done = run_virtue(root)
            later_ran = (root / "later-test-ran").exists()
        assert_that((done.returncode != 0, later_ran), equal_to((True, True)))


class TestTimingOfARealRun(unittest.TestCase):
    """virtue, given the session's reporter, ends the run with the timing."""

    def test_a_run_that_passes_prints_the_total_and_the_slowest(self) -> None:
        """The total line and a line for the test, in the output of the run."""
        with tempfile.TemporaryDirectory() as name:
            done = run_virtue(pathlib.Path(name), REPORTER, "-x")
        has_all(
            done.stdout,
            [
                f"\n{noxcheck.TIMING_PREFIX}total ",
                f"\n{noxcheck.TIMING_PREFIX}slowest 1 ",
                "twotests.TestTwo.test_a_fails",
            ],
        )

    def test_a_run_that_fails_prints_them_too(self) -> None:
        """The failing test stops the run (-x) and the timing is still printed."""
        with tempfile.TemporaryDirectory() as name:
            done = run_virtue(pathlib.Path(name), "-x", REPORTER)
        assert_that(done.returncode != 0, equal_to(True))
        has_all(done.stdout, ["this one fails", f"{noxcheck.TIMING_PREFIX}total "])

    def test_a_run_with_the_default_reporter_prints_no_timing(self) -> None:
        """The nearest input: virtue alone prints none, which is what this fixes."""
        with tempfile.TemporaryDirectory() as name:
            done = run_virtue(pathlib.Path(name), "-x")
        has_none(done.stdout, [noxcheck.TIMING_PREFIX])


class TestCiLogShowsTheTiming(unittest.TestCase):
    """CI's Run Nox step keeps the slowest-test list in its log."""

    def test_the_step_runs_nox_with_nothing_that_hides_its_output(self) -> None:
        """No quiet option, no silent run, no filter on the command (pitboss#324)."""
        workflow = (EXAMPLE.parents[1] / ".github/workflows/pr-main.yml").read_text()
        step = workflow.split("- name: Run Nox")[1].split("- name:")[0]
        has_all(step, ["nox --force-color --python=", "--session="])
        command = [line for line in step.splitlines() if "nox --force-color" in line]
        has_none(command[0], ["--quiet", " -q", "|", ">", "--no-"])

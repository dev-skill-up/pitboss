"""Tests for the leak check of the tests session (pitboss#346, keyword: test-leak)."""

import contextlib
import dataclasses
import io
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import noxcheck
from . import scratch, timingreport
from .briefmake import has_all, has_none
from .fakes import write

REPORTER = "--reporter=pitboss.tests.timingreport.TimingReporter"
PREFIX = noxcheck.LEAK_PREFIX

MIXED = """
import pathlib
import tempfile
import unittest

from pitboss.tests import scratch


class TestKinds(unittest.TestCase):
    def test_a_leaks(self) -> None:
        tempfile.mkdtemp(prefix="left-behind-")

    def test_b_removes_its_own(self) -> None:
        path = pathlib.Path(tempfile.mkdtemp(prefix="removed-"))
        self.addCleanup(path.rmdir)

    def test_c_uses_the_scratch_directory(self) -> None:
        scratch.directory()
"""
ALL_REMOVED = """
import pathlib
import tempfile
import unittest

from pitboss.tests import scratch


class TestKinds(unittest.TestCase):
    def test_b_removes_its_own(self) -> None:
        path = pathlib.Path(tempfile.mkdtemp(prefix="removed-"))
        self.addCleanup(path.rmdir)

    def test_c_uses_the_scratch_directory(self) -> None:
        scratch.directory()
"""
FAILING_AND_LEAKING = """
import tempfile
import unittest


class TestKinds(unittest.TestCase):
    def test_a_leaks_and_fails(self) -> None:
        tempfile.mkdtemp(prefix="left-behind-")
        self.fail("this one fails")
"""
LEAKING_CLASS = """
import tempfile
import unittest


class TestKinds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tempfile.mkdtemp(prefix="class-level-")

    def test_a_passes(self) -> None:
        pass
"""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ran:
    """A run of virtue with the session's reporter.

    Attributes:
        failed: whether virtue exited with a status.
        out: what it printed, standard error joined to standard output.
        left: the names left in the ``TMPDIR`` it was given.
    """

    failed: bool
    out: str
    left: Sequence[str]


def run_module(source: str, *options: str) -> Ran:
    """Run the real virtue, with the session's reporter, over a module.

    Args:
        source: the module's text.
        *options: the options for virtue.

    Returns:
        What the run did.
    """
    with tempfile.TemporaryDirectory() as name:
        root = pathlib.Path(name)
        (root / "tmp").mkdir()
        write(root / "leaktests.py", source)
        done = virtue_in(root, options)
        left = sorted(each.name for each in (root / "tmp").iterdir())
    return Ran(failed=bool(done.returncode), out=done.stdout, left=left)


def virtue_in(
    root: pathlib.Path, options: Sequence[str]
) -> subprocess.CompletedProcess[str]:
    """Run virtue over ``leaktests`` in a directory, with its ``tmp`` as ``TMPDIR``.

    Args:
        root: the directory, with ``leaktests.py`` and ``tmp`` in it.
        options: the options for virtue.

    Returns:
        The finished process, standard error joined to standard output.
    """
    command = [sys.executable, "-m", "virtue", *options, REPORTER, "leaktests"]
    environment = {**os.environ, "PYTHONPATH": str(root), "TMPDIR": str(root / "tmp")}
    return subprocess.run(
        command,
        cwd=root,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


class TestAPassingRunThatLeaves(unittest.TestCase):
    """A run that passes and left a name in its TMPDIR fails, naming the test."""

    def test_it_fails_and_names_the_test_that_left_it(self) -> None:
        """A line with the test's id, or the line that says no test left it."""
        cases = [
            (MIXED, "leaktests.TestKinds.test_a_leaks left-behind-"),
            (LEAKING_CLASS, f"{noxcheck.OUTSIDE_TESTS} class-level-"),
        ]
        for source, line in cases:
            ran = run_module(source)
            has_all(ran.out, [f"\n{PREFIX}{line}"])
            assert_that(ran.failed, equal_to(True))

    def test_the_tests_that_cleaned_up_are_not_named_and_the_timing_is_last(
        self,
    ) -> None:
        """Only the leak is named; the leak lines come before the timing."""
        ran = run_module(MIXED)
        has_none(ran.out, [f"{PREFIX}leaktests.TestKinds.test_{x}" for x in "bc"])
        last = ran.out.splitlines()[-1]
        found = (last.startswith(noxcheck.TIMING_PREFIX), len(ran.left))
        assert_that(found, equal_to((True, 1)))


class TestARunThatIsNotCheckedOrHasNoLeak(unittest.TestCase):
    """No leak line for a run that fails, or for one that cleaned up."""

    def test_the_nearest_inputs_to_the_leak_say_nothing_of_it(self) -> None:
        """Cleaned up by the test and by scratch; and failing while leaking (kept)."""
        cases = [
            (ALL_REMOVED, (), (False, False, 0, False)),
            (FAILING_AND_LEAKING, ("-x",), (False, True, 1, True)),
        ]
        for source, options, expected in cases:
            ran = run_module(source, *options)
            found = (
                PREFIX in ran.out,
                ran.failed,
                len(ran.left),
                "this one fails" in ran.out,
            )
            assert_that(found, equal_to(expected))


class TestLeakLines(unittest.TestCase):
    """The lines are the prefix, the test and the name."""

    def test_a_line_for_each_leak_in_order_and_none_for_none(self) -> None:
        """Two leaks of one test, then one of another; nothing left, nothing said."""
        leaks = [("m.T.a", "x"), ("m.T.a", "y"), ("m.T.b", "z")]
        expected = [f"{PREFIX}m.T.a x", f"{PREFIX}m.T.a y", f"{PREFIX}m.T.b z"]
        assert_that(timingreport.leak_lines(leaks), equal_to(expected))
        assert_that(timingreport.leak_lines([]), equal_to([]))


class Holder(unittest.TestCase):
    """A test for the directories to be registered with."""

    def runTest(self) -> None:  # noqa: N802,SLD303
        """Nothing runs."""


class TestScratch(unittest.TestCase):
    """Who removes the directories a test makes."""

    def test_the_running_tests_cleanup_removes_a_directory(self) -> None:
        """After the cleanups of the test that was running, the directory is gone."""
        holder = Holder()
        scratch.begin(holder)
        self.addCleanup(scratch.end)
        path = scratch.directory()
        existed = path.is_dir()
        holder.doCleanups()
        assert_that((existed, path.exists()), equal_to((True, False)))

    def test_a_directory_is_fresh_unless_the_process_owns_it(self) -> None:
        """No test runs, so nothing removes the first: the leak check finds it."""
        scratch.end()
        for make, owned in (
            (scratch.directory, False),
            (scratch.process_directory, True),
        ):
            before = scratch.listing()
            path = make()
            self.addCleanup(shutil.rmtree, path)
            self.addCleanup(scratch.OWNED.discard, path.name)
            found = (path.is_dir(), scratch.fresh(before, scratch.listing()))
            assert_that(found, equal_to((True, [] if owned else [path.name])))

    def test_a_world_built_once_is_built_once_in_the_process_scope(self) -> None:
        """The builder runs in the process scope once; a failing block ends it."""
        seen: list[bool] = []

        def make() -> int:
            seen.append(scratch.PROCESS.get())
            return len(seen)

        once = scratch.built_once(make)
        with contextlib.suppress(KeyError), scratch.process_wide():
            dict[str, str]().pop("missing")
        assert_that((once(), once(), seen), equal_to((1, 1, [True])))
        assert_that(scratch.PROCESS.get(), equal_to(False))

    def test_the_listing_of_a_missing_directory_is_empty(self) -> None:
        """TMPDIR that is not there is no names."""
        old = tempfile.tempdir
        tempfile.tempdir = "/nonexistent-directory-for-the-listing-test"
        self.addCleanup(setattr, tempfile, "tempdir", old)
        assert_that(scratch.listing(), equal_to(frozenset()))


class Case(unittest.TestCase):
    """A test for the reporter to be told about."""

    def test_one(self) -> None:
        """Only its id is used."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Script:
    """What happens in a run of one test.

    Attributes:
        kept: directories there before the run starts.
        before_test: directories made after the run starts and before the test
            does (a class's set-up).
        in_test: directories the test makes and leaves.
        reports: the reporter method that tells how the test went.
    """

    kept: int = 0
    before_test: int = 0
    in_test: int = 0
    reports: str = "addSuccess"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Said:
    """What a reporter said about a run of one test.

    Attributes:
        passed: the reporter's answer to ``wasSuccessful``.
        out: what it printed.
    """

    passed: bool
    out: str


def make_directories(prefix: str, count: int) -> None:
    """Make some temporary directories, as a test that leaves them would.

    Args:
        prefix: the start of their names.
        count: how many.
    """
    for _ in range(count):
        tempfile.mkdtemp(prefix=prefix)


def play(stream: io.StringIO, script: Script) -> bool:
    """Drive a reporter through a run of one test.

    Args:
        stream: where the reporter writes.
        script: what happens.

    Returns:
        The reporter's answer to ``wasSuccessful``.
    """
    reporter = timingreport.TimingReporter(stream=stream)
    case = Case("test_one")
    make_directories("kept-", script.kept)
    reporter.startTestRun()
    make_directories("before-", script.before_test)
    reporter.startTest(case)
    make_directories("in-test-", script.in_test)
    getattr(reporter, script.reports)(case)
    reporter.stopTest(case)
    reporter.stopTestRun()
    return bool(reporter.wasSuccessful())


def said_by(script: Script) -> Said:
    """Run a script through a reporter, in a temporary directory of its own.

    Args:
        script: what happens.

    Returns:
        What the reporter answered and printed.
    """
    running = scratch.TEST.get()
    old = tempfile.tempdir
    with tempfile.TemporaryDirectory() as top:
        tempfile.tempdir = top
        stream = io.StringIO()
        passed = play(stream, script)
        tempfile.tempdir = old
        scratch.TEST.set(running)
        return Said(passed=passed, out=stream.getvalue())


class TestTheReporterInProcess(unittest.TestCase):
    """The reporter's answer and lines, read where coverage sees them."""

    def test_a_leak_fails_the_run_and_a_line_names_who_left_it(self) -> None:
        """One line for each name: the test that left it, or the line that says none."""
        cases = [
            (Script(in_test=1), f"{PREFIX}{Case('test_one').id()} in-test-", 1),
            (Script(before_test=2), f"{PREFIX}{noxcheck.OUTSIDE_TESTS} before-", 2),
        ]
        for script, line, count in cases:
            said = said_by(script)
            assert_that((said.out.count(line), said.passed), equal_to((count, False)))

    def test_what_is_not_this_runs_or_not_green_is_no_leak(self) -> None:
        """A directory from before the run; and a red run, which keeps its own."""
        red = Script(in_test=1, before_test=1, reports="addUnexpectedSuccess")
        for script, passed in ((Script(kept=1), True), (red, False)):
            said = said_by(script)
            assert_that((said.passed, PREFIX in said.out), equal_to((passed, False)))
            has_all(said.out, [noxcheck.TIMING_PREFIX])

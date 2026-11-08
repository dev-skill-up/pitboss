"""Tests for the leak check of the tests session (pitboss#346, keyword: test-leak)."""

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

REPORTER = "--reporter=pitboss.tests.timingreport.TimingReporter"
LEAK = noxcheck.LEAK_PREFIX

LEAKY = """
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

    def test_c_uses_the_helper(self) -> None:
        scratch.directory()
"""
CLEAN = """
import pathlib
import tempfile
import unittest

from pitboss.tests import scratch


class TestKinds(unittest.TestCase):
    def test_b_removes_its_own(self) -> None:
        path = pathlib.Path(tempfile.mkdtemp(prefix="removed-"))
        self.addCleanup(path.rmdir)

    def test_c_uses_the_helper(self) -> None:
        scratch.directory()
"""
FAILING_AND_LEAKY = """
import tempfile
import unittest


class TestKinds(unittest.TestCase):
    def test_a_leaks_and_fails(self) -> None:
        tempfile.mkdtemp(prefix="left-behind-")
        self.fail("this one fails")
"""
LEAKY_CLASS = """
import tempfile
import unittest


class TestKinds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        tempfile.mkdtemp(prefix="class-level-")

    def test_a_passes(self) -> None:
        pass
"""


def run_module(
    source: str, *options: str
) -> tuple[subprocess.CompletedProcess[str], Sequence[str]]:
    """Run the real virtue, with the session's reporter, over a module.

    Args:
        source: the module's text.
        *options: the options for virtue.

    Returns:
        The finished process (standard error joined to standard output), and
        the names left in the ``TMPDIR`` it was given.
    """
    with tempfile.TemporaryDirectory() as name:
        root = pathlib.Path(name)
        (root / "leaktests.py").write_text(source)
        tmp = root / "tmp"
        tmp.mkdir()
        done = subprocess.run(
            [sys.executable, "-m", "virtue", *options, REPORTER, "leaktests"],
            cwd=root,
            env={**os.environ, "PYTHONPATH": str(root), "TMPDIR": str(tmp)},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        return done, sorted(each.name for each in tmp.iterdir())


class TestAPassingRunThatLeaves(unittest.TestCase):
    """A run that passes and left a name in its TMPDIR fails, naming the test."""

    def test_it_fails_and_names_the_test_that_left_the_directory(self) -> None:
        """A line for the leak, with the test's id; the tests that cleaned are not."""
        done, left = run_module(LEAKY)
        assert_that(done.returncode != 0, equal_to(True))
        named = f"\n{LEAK}leaktests.TestKinds.test_a_leaks left-behind-"
        has_all(done.stdout, [named])
        has_none(done.stdout, [f"{LEAK}leaktests.TestKinds.test_b"])
        has_none(done.stdout, [f"{LEAK}leaktests.TestKinds.test_c"])
        assert_that(len(left), equal_to(1))

    def test_a_leak_made_outside_any_test_is_named_as_such(self) -> None:
        """A class's set-up is no test's: the line says so."""
        done, _ = run_module(LEAKY_CLASS)
        assert_that(done.returncode != 0, equal_to(True))
        named = f"\n{LEAK}{noxcheck.OUTSIDE_TESTS} class-level-"
        has_all(done.stdout, [named])

    def test_the_timing_still_ends_the_output(self) -> None:
        """The leak lines come first and the timing is still the last."""
        done, _ = run_module(LEAKY)
        lines = done.stdout.splitlines()
        assert_that(lines[-1].startswith(noxcheck.TIMING_PREFIX), equal_to(True))

    def test_a_run_that_removes_what_it_makes_passes(self) -> None:
        """The nearest input: one directory removed by the test, one by the helper."""
        done, left = run_module(CLEAN)
        assert_that((done.returncode, left), equal_to((0, [])))
        has_none(done.stdout, [LEAK])


class TestAFailingRunIsNotChecked(unittest.TestCase):
    """A run that fails keeps its directory and says nothing about leaks."""

    def test_it_fails_for_its_own_reason_and_names_no_leak(self) -> None:
        """The failure is shown, the leak lines are not, the directory is kept."""
        done, left = run_module(FAILING_AND_LEAKY, "-x")
        assert_that(done.returncode != 0, equal_to(True))
        has_all(done.stdout, ["this one fails"])
        has_none(done.stdout, [LEAK])
        assert_that(len(left), equal_to(1))


class TestLeakLines(unittest.TestCase):
    """The lines are the prefix, the test and the name."""

    def test_a_line_for_each_leak_in_order(self) -> None:
        """Two leaks of one test, then one of another."""
        leaks = [("m.T.a", "x"), ("m.T.a", "y"), ("m.T.b", "z")]
        expected = [f"{LEAK}m.T.a x", f"{LEAK}m.T.a y", f"{LEAK}m.T.b z"]
        assert_that(timingreport.leak_lines(leaks), equal_to(expected))

    def test_no_leak_has_no_line(self) -> None:
        """Nothing left: nothing printed."""
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

    def test_a_directory_made_between_tests_stays(self) -> None:
        """No test runs, so nothing removes it: the leak check finds it."""
        scratch.end()
        path = scratch.directory()
        self.addCleanup(shutil.rmtree, path)
        assert_that(path.is_dir(), equal_to(True))

    def test_a_process_directory_is_owned_and_not_fresh(self) -> None:
        """Made inside process_wide, it is not a leak of the test that made it."""
        holder = Holder()
        scratch.begin(holder)
        self.addCleanup(scratch.end)
        before = scratch.listing()
        with scratch.process_wide():
            path = scratch.directory()
        self.addCleanup(shutil.rmtree, path)
        self.addCleanup(scratch.STATE.owned.discard, path.name)
        holder.doCleanups()
        assert_that(
            (path.is_dir(), scratch.fresh(before, scratch.listing())),
            equal_to((True, [])),
        )

    def test_a_name_that_appeared_and_is_not_owned_is_fresh(self) -> None:
        """The nearest input: made with no process scope, it is named."""
        before = scratch.listing()
        path = scratch.directory()
        self.addCleanup(shutil.rmtree, path)
        assert_that(scratch.fresh(before, scratch.listing()), equal_to([path.name]))

    def test_the_process_scope_ends_with_its_block(self) -> None:
        """Even when the block raises, the next directory is the test's again."""
        try:
            with scratch.process_wide():
                raise ValueError("inside")
        except ValueError:
            pass
        assert_that(scratch.STATE.process, equal_to(False))

    def test_a_world_built_once_is_built_once_in_the_process_scope(self) -> None:
        """The builder runs in process_wide on the first call only."""
        seen: list[bool] = []

        def make() -> int:
            seen.append(scratch.STATE.process)
            return len(seen)

        once = scratch.built_once(make)
        assert_that((once(), once(), seen), equal_to((1, 1, [True])))
        assert_that(scratch.STATE.process, equal_to(False))

    def test_a_process_directory_is_made_by_the_helper(self) -> None:
        """It is owned, and exists until the process ends."""
        path = scratch.process_directory()
        self.addCleanup(shutil.rmtree, path)
        self.addCleanup(scratch.STATE.owned.discard, path.name)
        assert_that(
            (path.is_dir(), path.name in scratch.STATE.owned), equal_to((True, True))
        )

    def test_the_listing_of_a_missing_directory_is_empty(self) -> None:
        """TMPDIR that is not there is no names."""
        with tempfile.TemporaryDirectory() as name:
            gone = pathlib.Path(name) / "gone"
            old = tempfile.tempdir
            tempfile.tempdir = str(gone)
            self.addCleanup(setattr, tempfile, "tempdir", old)
            found = scratch.listing()
        assert_that(found, equal_to(frozenset()))

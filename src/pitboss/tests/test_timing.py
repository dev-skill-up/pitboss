"""Tests for the timing of the tests session (pitboss#324, keyword: test-timing)."""

import io
import unittest

from hamcrest import assert_that, equal_to

from .. import expansion, noxcheck
from . import timingreport

PREFIX = noxcheck.TIMING_PREFIX


class TestTimingLines(unittest.TestCase):
    """The total, then the slowest tests, slowest first."""

    def test_the_total_and_the_count_come_first(self) -> None:
        """Two tests: the sum of their seconds and how many ran."""
        found = timingreport.timing_lines([(0.5, "a.A.test_x"), (1.25, "a.A.test_y")])
        assert_that(found[0], equal_to(f"{PREFIX}total 1.750s in 2 tests"))

    def test_the_slowest_come_slowest_first_with_their_times(self) -> None:
        """Numbered from 1; a tie is ordered by the test's name."""
        found = timingreport.timing_lines(
            [(0.5, "m.T.test_b"), (2.0, "m.T.test_c"), (0.5, "m.T.test_a")]
        )
        assert_that(
            found[1:],
            equal_to(
                [
                    f"{PREFIX}slowest 1 2.000s m.T.test_c",
                    f"{PREFIX}slowest 2 0.500s m.T.test_a",
                    f"{PREFIX}slowest 3 0.500s m.T.test_b",
                ]
            ),
        )

    def test_thirty_are_listed_and_not_more(self) -> None:
        """Thirty-one tests: the fastest is the one left out."""
        durations = [(float(each), f"m.T.test_{each}") for each in range(1, 32)]
        found = timingreport.timing_lines(durations)
        assert_that(len(found), equal_to(1 + noxcheck.SLOWEST_COUNT))
        assert_that(found[-1], equal_to(f"{PREFIX}slowest 30 2.000s m.T.test_2"))
        assert_that(found[0], equal_to(f"{PREFIX}total 496.000s in 31 tests"))

    def test_a_run_of_no_tests_has_a_total_and_no_list(self) -> None:
        """Nothing ran: the total line only."""
        assert_that(
            timingreport.timing_lines([]),
            equal_to([f"{PREFIX}total 0.000s in 0 tests"]),
        )


class Case(unittest.TestCase):
    """A test for the reporter to be told about."""

    def test_one(self) -> None:
        """Only its id is used."""


class TestReporter(unittest.TestCase):
    """The reporter prints the timing when the run stops."""

    def test_the_lines_follow_virtues_summary(self) -> None:
        """The durations unittest reports are what is printed, after Ran."""
        stream = io.StringIO()
        reporter = timingreport.TimingReporter(stream=stream)
        reporter.startTestRun()
        reporter.addDuration(Case("test_one"), 0.25)
        reporter.stopTestRun()
        shown = stream.getvalue().splitlines()
        expected = [
            f"{PREFIX}total 0.250s in 1 tests",
            f"{PREFIX}slowest 1 0.250s {Case('test_one').id()}",
        ]
        assert_that(shown[-2:], equal_to(expected))
        assert_that(any(line.startswith("Ran ") for line in shown), equal_to(True))

    def test_a_second_run_starts_from_none(self) -> None:
        """The durations are the run's own."""
        stream = io.StringIO()
        reporter = timingreport.TimingReporter(stream=stream)
        for _ in range(2):
            reporter.startTestRun()
            reporter.addDuration(Case("test_one"), 1.0)
        reporter.stopTestRun()
        shown = stream.getvalue()
        assert_that(f"{PREFIX}total 1.000s in 1 tests" in shown, equal_to(True))


class TestTimingOf(unittest.TestCase):
    """The lines of a session's output that are timing."""

    def test_only_the_lines_that_start_with_the_prefix(self) -> None:
        """Noise around them is left out."""
        step = noxcheck.Step(
            name="tests-3.13",
            outcome=expansion.Outcome(
                status=0, output=f"noise\n{PREFIX}total 1.000s in 1 tests\nmore\n"
            ),
            seconds=1,
        )
        assert_that(
            noxcheck.timing_of(step), equal_to([f"{PREFIX}total 1.000s in 1 tests"])
        )

    def test_a_line_that_only_holds_the_prefix_is_not_timing(self) -> None:
        """The nearest input: the prefix inside a line, not at its start."""
        step = noxcheck.Step(
            name="lint",
            outcome=expansion.Outcome(status=0, output=f"x {PREFIX}total\n"),
            seconds=1,
        )
        assert_that(noxcheck.timing_of(step), equal_to([]))

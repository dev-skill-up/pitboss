"""The log of a sweep's commands, its timing lines and its concurrent reads."""

import contextlib
import io
import itertools
import subprocess
import threading
import types
import unittest
from typing import Callable, Sequence, TextIO, cast

from hamcrest import (
    assert_that,
    contains_exactly,
    contains_string,
    equal_to,
    has_length,
)

from .. import calllog, concurrently, running, timing
from . import fakes, repositories


def ticks() -> Callable[[], float]:
    """A clock that moves on a second every time it is read.

    Returns:
        The clock, whose first reading is one second.
    """
    counter = itertools.count(1)
    return lambda: float(next(counter))


def _ok(cmdargs: Sequence[str], /, *args: object, **kwargs: object) -> fakes.Output:
    return fakes.Output(stdout="ok")


def _fails(cmdargs: Sequence[str], /, *args: object, **kwargs: object) -> fakes.Output:
    raise subprocess.CalledProcessError(1, list(cmdargs))


def run_logged(
    run: running.KeywordRun, log: calllog.Log, command: Sequence[str]
) -> None:
    """Run a command through a runner that logs, one second a reading.

    Args:
        run: the runner.
        log: the log.
        command: the command line.
    """
    calllog.logging_run(run, log, ticks())(command)


class TestKind(unittest.TestCase):
    """Alike commands count as one kind."""

    def test_api_paths_lose_the_repository_and_the_numbers(self) -> None:
        """Repository, numbers, commits and the query are not part of the kind."""
        sha = "a" * 40
        paths = [
            "repos/o/r/pulls?state=open&per_page=100&page=2",
            "repos/o/r/pulls/12/reviews",
            f"repos/o/r/commits/{sha}/check-runs",
            "repos/o/r",
        ]
        found = [calllog.kind_of(["gh", "api", path]) for path in paths]
        expected = [
            "gh api pulls",
            "gh api pulls/reviews",
            "gh api commits/check-runs",
            "gh api repository",
        ]
        assert_that(found, equal_to(expected))

    def test_a_post_is_its_path(self) -> None:
        """The last word of the line is the path, as it is for a read."""
        found = calllog.kind_of(["gh", "api", "-X", "POST", "repos/o/r/cancel"])
        assert_that(found, equal_to("gh api cancel"))

    def test_other_commands_are_their_first_two_words(self) -> None:
        """A git command is told by its first two words."""
        found = calllog.kind_of(["git", "-C", "/x", "fetch", "-q", "origin"])
        assert_that(found, equal_to("git -C"))

    def test_a_long_command_line_is_cut(self) -> None:
        """A name is at most ``NAME_LIMIT`` characters."""
        found = calllog.name_of(["gh", "api", "x" * 500])
        assert_that(found, has_length(calllog.NAME_LIMIT))
        assert_that(calllog.name_of(["gh", "api"]), equal_to("gh api"))


class TestLogged(unittest.TestCase):
    """The runner that logs."""

    def test_every_command_is_logged_with_its_time(self) -> None:
        """A command that ran, and one that raised, are both in the log."""
        log = calllog.new_log(0.0)
        run_logged(_ok, log, ["gh", "api", "repos/o/r/pulls"])
        with self.assertRaises(subprocess.CalledProcessError):
            run_logged(_fails, log, ["gh", "api", "repos/o/r/issues"])
        found = [(each.kind, each.seconds) for each in log.calls]
        expected = [("gh api pulls", 1.0), ("gh api issues", 1.0)]
        assert_that(found, equal_to(expected))

    def test_the_keywords_of_a_call_reach_the_runner_and_the_call_is_logged(
        self,
    ) -> None:
        """A positional argument and ``check``, ``capture_output``, ``text`` go on."""
        seen: list[tuple[Sequence[str], tuple[object, ...], dict[str, object]]] = []

        def runner(
            cmdargs: Sequence[str], /, *more: object, **keywords: object
        ) -> fakes.Output:
            seen.append((cmdargs, more, keywords))
            return fakes.Output(stdout="ok")

        log = calllog.new_log(0.0)
        wrapped = calllog.logging_run(runner, log, ticks())
        wrapped(["git", "status"], 5, check=True, capture_output=True, text=True)
        wanted = (
            ["git", "status"],
            (5,),
            dict(check=True, capture_output=True, text=True),
        )
        assert_that(seen, equal_to([wanted]))
        assert_that([each.name for each in log.calls], equal_to(["git status"]))

    def test_a_phase_ends_with_the_calls_since_the_last(self) -> None:
        """The next phase starts empty, where the last one ended."""
        log = calllog.new_log(5.0)
        clone = repositories.make_repository(fakes.directory())
        run_logged(fakes.FakeProcesses(bodies={}, cwd=clone), log, ["git", "status"])
        first = calllog.end_phase(log, 9.0)
        second = calllog.end_phase(log, 12.0)
        found = [first.seconds, len(first.calls), second.seconds, len(second.calls)]
        assert_that(found, equal_to([4.0, 1, 3.0, 0]))

    def test_tally_and_slowest(self) -> None:
        """Kinds are counted, most numerous first, and calls ranked by time."""
        calls = [
            calllog.Call(name="a", kind="gh api pulls", seconds=1.0),
            calllog.Call(name="b", kind="gh api issues", seconds=9.0),
            calllog.Call(name="c", kind="gh api pulls", seconds=3.0),
        ]
        phase = calllog.Phase(seconds=13.0, calls=calls)
        tallied = calllog.tally(phase)
        assert_that(tallied, equal_to({"gh api pulls": 2, "gh api issues": 1}))
        found = [each.name for each in calllog.slowest(phase, 2)]
        assert_that(found, contains_exactly("b", "c"))


def lap_of(seconds: float, calls: Sequence[calllog.Call]) -> str:
    """Say what ``lap`` prints on standard error for a section.

    Args:
        seconds: how long the section took.
        calls: what it ran.

    Returns:
        What it printed.
    """
    clock = timing.start()
    for each in calls:
        calllog.add(clock.log, each)
    clock.log.began[0] -= seconds
    with contextlib.redirect_stderr(io.StringIO()) as err:
        timing.lap(clock, "pull requests done")
    return err.getvalue()


class TestLap(unittest.TestCase):
    """The line a section ends with, on standard error."""

    def test_a_quick_section_says_its_count_and_kinds(self) -> None:
        """No call is named in a section under 30 seconds."""
        calls = [calllog.Call(name="gh api x", kind="gh api x", seconds=2.0)] * 2
        found = lap_of(5, calls)
        assert_that(found, contains_string("pull requests done: 5s, 2 commands"))
        assert_that("waited" in found, equal_to(False))
        assert_that("ran: gh api x 2" in found, equal_to(True))

    def test_a_slow_section_names_what_it_waited_for(self) -> None:
        """Over 30 seconds, the slowest commands are named with their time."""
        slow = calllog.Call(name="gh api repos/o/r/pulls", kind="k", seconds=21.5)
        quick = calllog.Call(name="gh api repos/o/r/issues", kind="k", seconds=0.5)
        found = lap_of(40, [quick, slow])
        expected = [
            "  waited 21.5s for gh api repos/o/r/pulls",
            "  waited 0.5s for gh api repos/o/r/issues",
        ]
        assert_that(found.splitlines()[-2:], equal_to(expected))

    def test_the_lines_so_far_are_flushed(self) -> None:
        """A pipe sees the lines printed before the section's line."""
        flushes: list[int] = []
        pipe = types.SimpleNamespace(write=len, flush=lambda: flushes.append(1))
        with contextlib.redirect_stdout(cast(TextIO, pipe)):  # noqa: SLD203
            lap_of(1, [])
        assert_that(flushes, equal_to([1]))

    def test_a_section_that_ran_nothing_has_no_kinds_line(self) -> None:
        """There is no ``ran:`` line without a command."""
        assert_that("ran:" in lap_of(1, []), equal_to(False))


class TestConcurrently(unittest.TestCase):
    """Doing a read for many things at once."""

    def test_results_keep_the_order_of_the_items(self) -> None:
        """The first item finishes last, and is still first."""
        release = threading.Event()

        def work(number: int) -> int:
            if number == 0:
                release.wait(5)
            else:
                release.set()
            return number

        assert_that(concurrently.each(work, [0, 1, 2]), equal_to([0, 1, 2]))
        assert_that(list(concurrently.as_ready(work, [0, 1, 2])), equal_to([0, 1, 2]))

    def test_the_calls_overlap(self) -> None:
        """Eight calls that wait for each other all finish."""
        barrier = threading.Barrier(8, timeout=5)

        def work(number: int) -> int:
            barrier.wait()
            return number

        assert_that(concurrently.each(work, range(8)), equal_to(list(range(8))))

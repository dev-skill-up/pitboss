"""The reads and walks ``slots next`` and ``clean-container`` make once (pitboss#453).

A run asks GitHub for a path once, reads a long list's pages together and walks a
path of the disk once, so that a command's time is the time of what it must read.
"""

import dataclasses
import json
import subprocess
import unittest
from typing import Mapping, MutableSequence, Sequence

from hamcrest import assert_that, equal_to

from .. import concurrently, dead, ghapi, ghmemo, measured, scanning, survey
from . import fakes, world

MEMO_PATH = "repos/owner/project/issues/9"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Counting:
    """A runner that counts what it is asked and fails the paths it is told to.

    Attributes:
        asked: every command line run.
        failing: the path whose read fails.
    """

    asked: MutableSequence[Sequence[str]]
    failing: str = ""

    def __call__(
        self, cmdargs: Sequence[str], /, *args: object, **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Run a command.

        Args:
            cmdargs: the command line.
            *args: other positional arguments.
            **kwargs: keywords.

        Returns:
            The finished process.

        Raises:
            subprocess.CalledProcessError: for the failing path.
        """
        self.asked.append(list(cmdargs))
        if cmdargs[-1] == self.failing:
            raise subprocess.CalledProcessError(1, list(cmdargs), stderr="gone")
        return subprocess.CompletedProcess(list(cmdargs), 0, stdout="answer", stderr="")


def fail() -> int:
    """Fail as a read of GitHub does.

    Returns:
        Nothing: it always raises.

    Raises:
        subprocess.CalledProcessError: always.
    """
    raise subprocess.CalledProcessError(1, ["gh"])


class TestTheReadMemo(unittest.TestCase):
    """A read of ``gh api`` is made once in a run."""

    def test_a_second_ask_takes_the_first_answer(self) -> None:
        """Two asks of one path, one command."""
        runner = Counting(asked=[])
        reading = ghmemo.memoized(runner)
        command = ["gh", "api", MEMO_PATH]
        first, second = reading(command), reading(command)
        assert_that(
            (first.stdout, second.stdout, len(runner.asked)),
            equal_to(("answer", "answer", 1)),
        )

    def test_asks_at_the_same_time_make_one_command(self) -> None:
        """Sixteen threads ask for one path: one command."""
        runner = Counting(asked=[])
        reading = ghmemo.memoized(runner)
        command = ["gh", "api", MEMO_PATH]
        answers = concurrently.each(lambda _: reading(command).stdout, range(16))
        assert_that((set(answers), len(runner.asked)), equal_to(({"answer"}, 1)))

    def test_a_failed_read_fails_again_with_the_same_error(self) -> None:
        """The error is the first asker's, raised for each asker."""
        runner = Counting(asked=[], failing=MEMO_PATH)
        reading = ghmemo.memoized(runner)
        command = ["gh", "api", MEMO_PATH]
        said = []
        for _ in range(2):
            with self.assertRaises(subprocess.CalledProcessError) as caught:
                reading(command)
            said.append(str(caught.exception.stderr))
        assert_that((said, len(runner.asked)), equal_to((["gone", "gone"], 1)))

    def test_another_command_is_not_remembered(self) -> None:
        """A write, a read with keywords and another program run each time."""
        runner = Counting(asked=[])
        reading = ghmemo.memoized(runner)
        reading(["gh", "api", "-X", "POST", MEMO_PATH])
        reading(["gh", "api", "-X", "POST", MEMO_PATH])
        reading(["gh", "api", MEMO_PATH], check=True)
        reading(["gh", "api", MEMO_PATH], check=True)
        reading(["git", "status"])
        reading(["git", "status"])
        assert_that(len(runner.asked), equal_to(6))


def github_over(
    bodies: Mapping[str, object],
) -> tuple[ghapi.GitHub, Sequence[Sequence[str]]]:
    """An API over canned bodies.

    Args:
        bodies: the bodies by path.

    Returns:
        The API and the command lines it has run (a list that grows).
    """
    processes = fakes.FakeProcesses(bodies=dict(bodies))
    return ghapi.GitHub(run=processes, mutate=processes), processes.calls


class TestPagesAtOnce(unittest.TestCase):
    """The pages after the first of a long list are read together."""

    @staticmethod
    def parse(text: str) -> Sequence[int]:
        """Read a page.

        Args:
            text: the JSON.

        Returns:
            The numbers.
        """
        found = json.loads(text)
        assert isinstance(found, list)
        return found

    def test_a_short_first_page_is_the_list(self) -> None:
        """One call."""
        github, calls = github_over({fakes.page("list"): [1, 2]})
        found = ghapi.pages_at_once(github, "list", self.parse, 5)
        assert_that((found, len(calls)), equal_to(([1, 2], 1)))

    def test_a_long_list_reads_every_page_once_in_order(self) -> None:
        """The pages after the first are asked for, each once."""
        full = list(range(ghapi.PAGE_SIZE))
        bodies = {
            fakes.page("list", 1): full,
            fakes.page("list", 2): full,
            fakes.page("list", 3): [7],
        }
        github, calls = github_over(bodies)
        found = ghapi.pages_at_once(github, "list", self.parse, 3)
        assert_that(len(found), equal_to(2 * ghapi.PAGE_SIZE + 1))
        assert_that(len(calls), equal_to(3))

    def test_one_page_is_all_a_limit_of_one_reads(self) -> None:
        """A full first page and a limit of one: no second call."""
        full = list(range(ghapi.PAGE_SIZE))
        github, calls = github_over({fakes.page("list"): full})
        found = ghapi.pages_at_once(github, "list", self.parse, 1)
        assert_that((len(found), len(calls)), equal_to((len(full), 1)))


class TestThePairOfReads(unittest.TestCase):
    """Two reads that do not wait for each other."""

    def test_both_results_come_back_in_order(self) -> None:
        """Different types, one each."""
        assert_that(concurrently.pair(lambda: 1, lambda: "two"), equal_to((1, "two")))

    def test_a_failure_is_raised_once_both_have_finished(self) -> None:
        """The error of a read is not lost."""

        with self.assertRaises(subprocess.CalledProcessError):
            concurrently.pair(fail, lambda: "two")


class TestTheMemoOfWalks(unittest.TestCase):
    """A path two lists name is walked once."""

    def test_a_path_is_walked_once(self) -> None:
        """The second ask takes the survey of the first."""
        walked: list[object] = []

        def walk(path: object) -> survey.Survey:
            walked.append(path)
            return survey.Survey(size=len(walked))

        remembering = scanning.memo(walk)
        place = fakes.directory()
        assert_that(
            (remembering(place).size, remembering(place).size, len(walked)),
            equal_to((1, 1, 1)),
        )

    def test_an_untimed_scan_walks_each_time(self) -> None:
        """The default scan keeps nothing and says nothing."""
        scan = scanning.Scanning()
        scan.lap("section", 3, "things")
        assert_that((scan.walks, scan.lap is scanning.untimed), equal_to((None, True)))


class TestTheEarlyOut(unittest.TestCase):
    """A path changed after the cutoff is in use, whatever it holds."""

    def test_a_path_changed_after_the_cutoff_is_recent(self) -> None:
        """The path's own time decides."""
        place = fakes.directory()
        stamp = place.stat().st_mtime
        assert_that(
            (dead.recent(place, stamp - 10), dead.recent(place, stamp + 10)),
            equal_to((True, False)),
        )

    def test_a_missing_path_is_not_recent(self) -> None:
        """Nothing to judge."""
        place = fakes.directory() / "gone"
        assert_that(dead.recent(place, 0.0), equal_to(False))


PHASES = (
    "checkouts read",
    "repositories fetched",
    "checkouts, scratch and root files judged",
    "test tempdirs judged",
    "named scratch judged",
    "paths removed",
)


class TestTheBreakdown(unittest.TestCase):
    """``clean-container`` prints its timing breakdown by phase."""

    def test_each_phase_is_named(self) -> None:
        """The sections of the scan, the tempdirs and the removal."""
        here = dataclasses.replace(world.make_world(), kind=measured.MeasuredParser)
        said = world.again(here, "clean-container").err
        assert_that([each for each in PHASES if each not in said], equal_to([]))

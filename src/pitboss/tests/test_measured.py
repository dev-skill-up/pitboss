"""The timing lines that end a command (keyword: timing-lines, pitboss#443)."""

import argparse
import contextlib
import dataclasses
import io
import itertools
import subprocess
import unittest
from typing import Callable, Mapping, Sequence

from hamcrest import (
    assert_that,
    equal_to,
    has_length,
    is_,
    matches_regexp,
)

from .. import breakdown, calllog, cli_parser, measured, startup, timing
from . import fakes, fixeddisk, world
from .says import lacks, says
from .test_commands import sweep
from .test_slot_commands import next_result

PREFIX = breakdown.PREFIX


def ticks(step: float) -> Callable[[], float]:
    """A fake monotonic clock: each reading is a step after the last.

    Args:
        step: the seconds each reading advances.

    Returns:
        The clock.
    """
    readings = itertools.count(1)
    return lambda: next(readings) * step


def calling(*commands: Sequence[str]) -> measured.Command:
    """A command that runs some processes through the arguments' runner.

    Args:
        *commands: the command lines it runs, in order.

    Returns:
        The command.
    """

    def run(*, args: argparse.Namespace) -> None:
        for each in commands:
            args.safe_run(each)

    return run


def namespace(**names: object) -> argparse.Namespace:
    """Arguments whose runner answers every command with nothing.

    Args:
        **names: more arguments.

    Returns:
        The arguments.
    """
    return argparse.Namespace(
        safe_run=lambda command, /: fakes.Output(stdout=""), **names
    )


def timed(command: measured.Command, args: argparse.Namespace) -> Sequence[str]:
    """Run a command with fake clocks and give its standard error.

    Args:
        command: the command.
        args: the arguments.

    Returns:
        The lines it printed on standard error.
    """
    err = io.StringIO()
    wrapped = measured.Measured(command=command, read=ticks(0.5), began=lambda: 2.0)
    with contextlib.redirect_stderr(err):
        wrapped(args=args)
    return err.getvalue().splitlines()


def measuring(here: world.World) -> world.World:
    """The world, with the parser the real command line has.

    Args:
        here: the world.

    Returns:
        The same world, whose commands end with their breakdown.
    """
    return dataclasses.replace(here, kind=measured.MeasuredParser)


class TestTheLines(unittest.TestCase):
    """The seconds and the counts of each kind of work, on a fake clock."""

    def test_the_counts_and_seconds_of_each_kind(self) -> None:
        """Two gh calls, a git call and another: counted, with the seconds waited."""
        command = calling(
            ["gh", "api", "repos/o/r/pulls"],
            ["gh", "api", "repos/o/r/issues"],
            ["git", "fetch"],
            ["uvx", "something"],
        )
        found = timed(command, namespace(__gather_name__="slots", action="next"))
        work = "GitHub API 2 calls 1.0s, git 1 calls 0.5s, other processes 1 calls 0.5s"
        head = f"{PREFIX}slots next: 4.5s in the command, startup before it 2.0s"
        assert_that(
            found,
            equal_to([head, f"{PREFIX}rest: 4.5s; {work}", f"{PREFIX}all: {work}"]),
        )

    def test_a_section_is_told_with_its_count(self) -> None:
        """A noted section has its seconds, its count and its own commands."""

        def run(*, args: argparse.Namespace) -> None:
            args.safe_run(["gh", "api", "repos/o/r/pulls"])
            timing.note(args, "ranking", 3, "items")

        found = timed(run, namespace(__gather_name__="sweep"))
        says(found[0], "sweep: ")
        says(found[1], "ranking: 1.5s, 3 items; GitHub API 1")
        says(found[-1], "all: GitHub API 1 calls 0.5s")

    def test_nothing_noted_and_no_time_has_no_rest_section(self) -> None:
        """A command that ran nothing and took under a tenth of a second."""
        clock = timing.start(ticks(0.01))
        lines = timing.finish(clock, "lint pr-body", None)
        assert_that(lines, has_length(2))
        says(lines[0], "startup before it unknown")

    def test_a_failing_command_still_prints_its_lines(self) -> None:
        """The lines come out whatever the command did."""

        def fail(*, args: argparse.Namespace) -> None:
            raise RuntimeError(str(args))

        err = io.StringIO()
        wrapped = measured.Measured(command=fail, read=ticks(1.0), began=lambda: None)
        with contextlib.redirect_stderr(err), self.assertRaises(RuntimeError):
            wrapped(args=namespace(__gather_name__="lint", kind="pr-body"))
        says(err.getvalue(), "pitboss timing: lint pr-body: ")

    def test_a_command_is_named_by_its_word_and_its_action_or_kind(self) -> None:
        """The name, then the action, else the kind, else nothing more."""
        cases = [
            (namespace(__gather_name__="slots", action="next"), "slots next"),
            (namespace(__gather_name__="lint", kind="pr-body"), "lint pr-body"),
            (namespace(__gather_name__="sweep"), "sweep"),
        ]
        for args, wanted in cases:
            with self.subTest(wanted):
                assert_that(measured.name_of(args), equal_to(wanted))


class TestTheCommandsThatAreMeasured(unittest.TestCase):
    """Which commands end with the lines, through the real parser."""

    def test_slots_next_ends_with_its_breakdown_on_standard_error(self) -> None:
        """The last lines are the breakdown: the total, sections, all kinds."""
        shown = next_result(measuring(world.make_world()))
        lines = shown.err.splitlines()
        tail = [each for each in lines if each.startswith(PREFIX)]
        assert_that(lines[-len(tail) :], equal_to(tail))
        says(tail[0], "slots next: ")
        assert_that(tail[-1], matches_regexp(PREFIX + r"all: GitHub API \d+ calls"))
        says(" ".join(tail), "world read and decided: ", "lists and briefs printed: ")

    def test_the_sweep_ends_with_its_breakdown_too(self) -> None:
        """The sweep keeps the clock the command gave it: one set of lines."""
        shown = sweep(measuring(world.make_world()))
        lines = [each for each in shown.err.splitlines() if each.startswith(PREFIX)]
        says(lines[0], "sweep: ")
        assert_that(lines[-1], matches_regexp(PREFIX + r"all: GitHub API \d+ calls"))

    def test_a_command_that_is_not_in_the_list_is_not_measured(self) -> None:
        """``--help`` and the unlisted commands end with no line."""
        shown = world.invoke(measuring(world.make_world()), "slots", "--help")
        lacks(shown.err, PREFIX)

    def test_the_commands_of_the_ticket_are_measured_and_the_others_are_not(
        self,
    ) -> None:
        """The six commands of the ticket's Done-when, parsed as typed."""
        words = {
            "slots": ["slots", "next"],
            "sweep": ["sweep"],
            "plan-check": ["plan-check", __file__],
            "body-digest": ["body-digest", __file__],
            "lint": ["lint", "text", __file__],
            "clean-container": ["clean-container"],
            "next": ["next"],
        }
        kind = measured.MeasuredParser
        parser = cli_parser.make_parser(fixeddisk.fixed_usage, kind=kind)
        found = {
            name: isinstance(
                parser.parse_args(each).__gather_command__, measured.Measured
            )
            for name, each in words.items()
        }
        assert_that(found, equal_to({**dict.fromkeys(words, True), "next": False}))
        assert_that(sorted(measured.NAMES), equal_to(sorted(words.keys() - {"next"})))

    def test_a_default_that_is_not_a_command_is_left_alone(self) -> None:
        """A parser sets a default that is no function: it stays as it is."""
        parser = measured.MeasuredParser()
        parser.set_defaults(__gather_command__="text", __gather_name__="slots")
        assert_that(parser.get_default("__gather_command__"), equal_to("text"))


def proc_files(parent: str, launcher: str) -> Mapping[str, str]:
    """The files of ``/proc`` of a process started by some program.

    Args:
        parent: the parent's process number.
        launcher: the parent's program.

    Returns:
        The files by path.
    """
    zeros = "0 " * 17
    return {
        "/proc/uptime": "1000.0 5.0",
        "/proc/self/stat": f"7 (a b) S {parent} {zeros}5000 0",
        f"/proc/{parent}/stat": f"{parent} (uv) S 1 {zeros}4000 0",
        f"/proc/{parent}/comm": f"{launcher}\n",
    }


class TestTheStartup(unittest.TestCase):
    """The seconds before the command, read from the system's own record."""

    def test_a_process_started_by_uv_counts_from_uv(self) -> None:
        """The age is that of the launcher; any other parent leaves it alone."""
        cases = [("uv", 1000.0 - 40.0), ("bash", 1000.0 - 50.0)]
        for launcher, wanted in cases:
            with self.subTest(launcher):
                read = proc_files("9", launcher).__getitem__
                assert_that(startup.age(read, 100), equal_to(wanted))

    def test_a_system_without_proc_does_not_say(self) -> None:
        """A missing file, or one that does not read as the record, is unknown."""

        def missing(path: str) -> str:
            raise FileNotFoundError(path)

        assert_that(startup.age(missing, 100) is None, "a missing file")
        assert_that(startup.age(lambda path: "x", 100) is None, "a bad record")

    def test_the_file_of_proc_is_read_as_text(self) -> None:
        """The real reader gives the text of a file."""
        assert_that(float(startup.read_file("/proc/uptime").split()[0]) > 0, is_(True))

    def test_the_real_age_is_a_number_of_seconds(self) -> None:
        """This process began some time ago."""
        found = startup.age()
        assert_that(found is None or found > 0, is_(True))


class TestTheCallsAreCounted(unittest.TestCase):
    """The kinds of work, from the commands a fake GitHub saw."""

    def test_the_kind_of_each_command(self) -> None:
        """``gh`` and ``git`` are told apart from the rest."""
        names = ["gh api x", "git fetch", "uv run", ""]
        calls = [calllog.Call(name=each, kind=each, seconds=0.0) for each in names]
        kinds = [breakdown.family_of(each) for each in calls]
        other = "other processes"
        assert_that(kinds, equal_to(["GitHub API", "git", other, other]))

    def test_a_fake_github_that_records_its_calls_is_counted(self) -> None:
        """The runner of the arguments is the one the log wraps."""
        fake = fakes.FakeProcesses(bodies={"repos/o/r": {"id": 1}})
        clock = timing.start(ticks(1.0))
        args = timing.logged_args(argparse.Namespace(safe_run=fake), clock)
        args.safe_run(["gh", "api", "repos/o/r"])
        with contextlib.suppress(subprocess.CalledProcessError):
            args.safe_run(["gh", "api", "repos/o/missing"])
        says("\n".join(timing.finish(clock, "x", 0.0)), "GitHub API 2 calls")

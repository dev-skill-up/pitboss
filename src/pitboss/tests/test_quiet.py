"""The quiet period: the record, ``pressure``, ``queued`` and ``push``."""

import datetime
import pathlib
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to, starts_with

from .. import record
from . import fakes, test_config, world

PROJECT_JOBS = world.project_page("actions/runs/11/jobs")
START = world.START
GIT_ANSWERS = {"grep": 0, "mount": 1, "git": 0}
# Git's arguments come before the options: argparse in Python 3.12.3 rejects
# a positional list that follows an option (keyword: argparse-order).
PUSH = ("push", "origin", "branch-1", "--no-dry-run")


def at(minute: int) -> str:
    """The ``--now`` argument of a minute of the tests' hour.

    Args:
        minute: minutes after the start.

    Returns:
        The argument's value.
    """
    return (START + datetime.timedelta(minutes=minute)).isoformat()


def clear_world(answers: fakes.Answers = GIT_ANSWERS) -> world.World:
    """A world whose runners have no job waiting.

    Args:
        answers: the exit status of the programs that are not run.

    Returns:
        The world.
    """
    here = world.make_world(answers)
    here.bodies[PROJECT_JOBS] = {"jobs": []}
    return here


def record_path(here: world.World) -> pathlib.Path:
    """The record of a world, in its main clone's git directory.

    Args:
        here: the world.

    Returns:
        The path.
    """
    return here.clone / ".git" / "pitboss-pressure.log"


def lines(here: world.World) -> Sequence[str]:
    """The lines of a world's record.

    Args:
        here: the world.

    Returns:
        The lines; none when there is no file.
    """
    path = record_path(here)
    return path.read_text().splitlines() if path.exists() else []


def write(here: world.World, text: str) -> None:
    """Replace a world's record.

    Args:
        here: the world.
        text: the new text.
    """
    record_path(here).write_text(text)


def hold_at(minute: int) -> str:
    """The record line of a hold.

    Args:
        minute: minutes after the start.

    Returns:
        The line, with its newline.
    """
    return f"{at(minute)} hold\n".replace(".000000", "")


def pushes(here: world.World) -> int:
    """How many times the world ran ``git push``.

    Args:
        here: the world.

    Returns:
        The count.
    """
    return len([call for call in here.calls if list(call[:2]) == ["git", "push"]])


def exit_code(here: world.World, command: str, minute: int, *more: str) -> object:
    """Run a command at a minute and give its exit code.

    Args:
        here: the world.
        command: the command.
        minute: minutes after the start.
        *more: arguments after the config.

    Returns:
        The exit code.
    """
    return world.again(here, command, "--now", at(minute), *more).code


HOLD = (
    "HOLD pushes to non-draft PRs, undrafts, enqueues, merges and re-runs"
    " (all repositories; pushes to drafts are free)"
)
WAITING = (
    "RUNNER PRESSURE: 1 queue-run jobs waiting for a runner: "
    f"{HOLD}; 15 quiet minutes remain"
)
QUIET = (
    "RUNNER PRESSURE: nothing waits now, but a job waited or was put on the queue"
    f" within the quiet period; 15 quiet minutes remain: {HOLD}"
)
CLEAR = "NO RUNNER PRESSURE: push and merge as usual"


class TestPressure(unittest.TestCase):
    """``pressure`` against the record."""

    def test_lines(self) -> None:
        """Waiting, a quiet period to go, and over: one line each."""
        waiting = world.make_world(GIT_ANSWERS)
        first = clear_world()
        later = clear_world()
        write(later, hold_at(-60))
        worlds = [(waiting, 0), (first, 0), (later, 0)]
        found = [
            world.again(each, "pressure", "--now", at(minute))
            for each, minute in worlds
        ]
        lasts = [result.out.splitlines()[-1] for result in found]
        written = [lines(each)[-1] for each, _ in worlds]
        assert_that(
            (lasts, [result.code for result in found], written),
            equal_to(
                (
                    [WAITING, QUIET, CLEAR],
                    [1, 1, 0],
                    [f"{at(0)} hold", f"{at(0)} none", f"{at(0)} none"],
                )
            ),
        )

    def test_newest_hold_decides(self) -> None:
        """A hold 14 minutes old gives exit 1 with the minute left, 16 gives 0."""
        found = []
        for minute in (14, 16):
            here = clear_world()
            write(here, hold_at(0))
            result = world.again(here, "pressure", "--now", at(minute))
            found.append((result.code, "1 quiet minutes remain" in result.out))
        assert_that(found, equal_to([(1, True), (0, False)]))

    def test_exactly_the_quiet_period(self) -> None:
        """A hold exactly the quiet period old is over; a second short is not."""
        here = clear_world()
        write(here, hold_at(0))
        short = (START + datetime.timedelta(minutes=14, seconds=59)).isoformat()
        found = (
            world.again(here, "pressure", "--now", short).code,
            exit_code(here, "pressure", 15),
        )
        assert_that(found, equal_to((1, 0)))

    def test_each_call_appends_a_line(self) -> None:
        """A clear look is a none line; the record starts as no file."""
        here = clear_world()
        first = exit_code(here, "pressure", 0)
        second = exit_code(here, "pressure", 15)
        found = (first, second, lines(here))
        expected = (1, 0, [f"{at(0)} none", f"{at(15)} none"])
        assert_that(found, equal_to(expected))

    def test_empty_record(self) -> None:
        """An empty record has seen no quiet period yet."""
        here = clear_world()
        write(here, "")
        found = (exit_code(here, "pressure", 5), exit_code(here, "pressure", 20))
        assert_that(found, equal_to((1, 0)))

    def test_cut_line_is_not_glued(self) -> None:
        """A last line that was cut short counts as a hold and is not glued."""
        here = clear_world()
        write(here, f"{at(0)} no")
        found = (exit_code(here, "pressure", 20), lines(here))
        assert_that(found, equal_to((1, [f"{at(0)} no", f"{at(20)} none"])))

    def test_malformed_lines_are_holds(self) -> None:
        """A line that cannot be read never makes a quiet period that was not seen."""
        found = []
        for text, minute in (
            ("garbage\n", 100),
            (hold_at(0) + "x y z\n", 20),
            (hold_at(0) + "yesterday hold\n", 20),
            (hold_at(0) + "2030-01-01T00:00:00 none\n", 20),
            (hold_at(0) + f"{at(0)} maybe\n", 20),
            (hold_at(0) + "nonsense\n" + f"{at(5)} none\n", 14),
            ("\n\n  \n", 5),
        ):
            here = clear_world()
            write(here, text)
            found.append(exit_code(here, "pressure", minute))
        assert_that(found, equal_to([1] * 7))

    def test_malformed_line_ages_out(self) -> None:
        """A bad line is a hold at its next good line, so it does not block for good."""
        here = clear_world()
        write(here, "garbage\n" + f"{at(0)} none\n")
        found = (exit_code(here, "pressure", 14), exit_code(here, "pressure", 15))
        assert_that(found, equal_to((1, 0)))

    def test_undecodable_bytes(self) -> None:
        """Bytes that are not UTF-8 are a bad line."""
        here = clear_world()
        record_path(here).write_bytes(b"\xff\xfe\n")
        assert_that(exit_code(here, "pressure", 100), equal_to(1))

    def test_unusable_record(self) -> None:
        """A record that is a directory stops the command, naming it."""
        here = clear_world()
        record_path(here).mkdir()
        result = world.again(here, "pressure", "--now", at(0))
        assert_that(str(result.code), starts_with("cannot read the pressure record"))

    def test_quiet_minutes_key(self) -> None:
        """The quiet period is the configured one."""
        here = clear_world()
        with open(here.config, "a", encoding="utf-8") as stream:
            stream.write(
                "\n[runners]\nquiet_minutes = 3\nrecord = '%s'\n"
                % (here.workspace / "mine.log")
            )
        (here.workspace / "mine.log").write_text(hold_at(0))
        found = (exit_code(here, "pressure", 2), exit_code(here, "pressure", 3))
        assert_that((found, lines(here)), equal_to(((1, 0), [])))


class TestQueued(unittest.TestCase):
    """``queued`` and ``push`` restart the quiet period."""

    def test_queued_after_a_clear_look(self) -> None:
        """A queued job restarts the wait that a clear look had ended."""
        here = clear_world()
        write(here, hold_at(0))
        found = [
            exit_code(here, "pressure", 15),
            exit_code(here, "queued", 16),
            exit_code(here, "pressure", 30),
            exit_code(here, "pressure", 31),
        ]
        assert_that(found, equal_to([0, 0, 1, 0]))
        said = world.again(here, "queued", "--now", at(40)).out
        assert_that(said, starts_with(f"recorded a queued job at {at(40)}: the quiet"))

    def test_refused_push_changes_nothing(self) -> None:
        """A push in the quiet period is refused and leaves the record as it was."""
        here = clear_world()
        exit_code(here, "queued", 0)
        before = record_path(here).read_text()
        result = world.again(here, *PUSH, "--now", at(10))
        found = (result.code, record_path(here).read_text() == before, pushes(here))
        assert_that(found, equal_to((1, True, 0)))
        assert_that(exit_code(here, "pressure", 15), equal_to(0))

    def test_push_that_goes_out(self) -> None:
        """A push at minute 16 goes out, records a hold and holds until minute 31."""
        here = clear_world()
        exit_code(here, "queued", 0)
        pushed = world.again(here, "push", "origin", "--now", at(16), "--no-dry-run")
        found = [
            pushed.code,
            pushes(here),
            lines(here)[-1],
            exit_code(here, "pressure", 30),
            exit_code(here, "pressure", 31),
        ]
        assert_that(found, equal_to([0, 1, f"{at(16)} hold", 1, 0]))
        assert_that(
            ["git", "push", "origin"] in [list(c) for c in here.calls], equal_to(True)
        )

    def test_pushes_that_do_not_record(self) -> None:
        """Under pressure, in a dry run, when git fails or to a draft: no hold."""
        seed = hold_at(-60)
        failing = {"grep": 0, "mount": 1, "git": 3}
        cases = [
            (world.make_world(GIT_ANSWERS), ("--no-dry-run",), (1, 0)),
            (clear_world(), (), (0, 0)),
            (clear_world(failing), ("--no-dry-run",), (3, 1)),
            (world.make_world(GIT_ANSWERS), ("--no-dry-run", "--draft"), (0, 1)),
        ]
        found = []
        for here, options, _ in cases:
            write(here, seed)
            result = world.again(here, "push", "--now", at(0), *options)
            found.append(((result.code, pushes(here)), lines(here)))
        expected = [(each[2], [seed.strip()]) for each in cases]
        assert_that(found, equal_to(expected))


class TestRecord(unittest.TestCase):
    """The record's file and lines."""

    def test_quiet_keys(self) -> None:
        """The record is in the main clone's git directory, and quiet is 15."""
        directory = fakes.directory()
        given = fakes.settings(fakes.directory(), test_config.EVERYTHING).runners
        default = fakes.settings(directory).runners
        assert_that((given.quiet_minutes, default.quiet_minutes), equal_to((7, 15)))
        assert_that(given.record, equal_to(pathlib.Path("/somewhere/pressure.log")))
        assert_that(default.record.name, equal_to("pitboss-pressure.log"))
        assert_that(default.record.parent, equal_to(directory / "project" / ".git"))

    def test_file(self) -> None:
        """A missing file reads empty; appending makes it."""
        path = fakes.directory() / "log"
        before = record.read(path)
        record.append(path, "one\n")
        record.append(path, "two\n")
        assert_that((before, record.read(path)), equal_to(("", "one\ntwo\n")))

    def test_unwritable(self) -> None:
        """A path under a file cannot be written, and the command stops."""
        directory = fakes.directory()
        (directory / "file").write_text("x")
        try:
            record.append(directory / "file" / "log", "x")
        except SystemExit as stopped:
            message = str(stopped)
        assert_that(message, starts_with("cannot write the pressure record"))

    def test_remaining_rounds_up(self) -> None:
        """Part of a minute owed is a minute."""
        entries = [record.Entry(time=START, look=record.Look.HOLD)]
        now = START + datetime.timedelta(minutes=14, seconds=1)
        assert_that(record.minutes_remaining(entries, 15, now), equal_to(1))

"""The tracefs mount: three cases, with the mount command injected."""

import dataclasses
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import disk, tracefs
from . import fakes, world

FOUND = "tracefs: found mounted"
MOUNTED = "tracefs: mounted"
FAILED = "tracefs: NOT MOUNTED (mount exit status 32)"
NO_MOUNTS_FILE = 2


def line(answers: Mapping[str, int]) -> tuple[str, Sequence[str]]:
    """What ``ensure`` says and runs for the exit statuses of the programs.

    Args:
        answers: the exit status of ``grep`` and of ``mount``.

    Returns:
        The line, and the programs run.
    """
    machine = fakes.FakeProcesses(bodies={}, answers=answers)
    return tracefs.ensure(machine), [call[0] for call in machine.calls]


class TestEnsure(unittest.TestCase):
    """The idempotent mount."""

    def test_found_mounted(self) -> None:
        """A tracefs in /proc/mounts is left alone."""
        assert_that(line({"grep": 0, "mount": 1}), equal_to((FOUND, ["grep"])))

    def test_mounted(self) -> None:
        """An unmounted tracefs is mounted."""
        expected = (MOUNTED, ["grep", "mount"])
        assert_that(line({"grep": 1, "mount": 0}), equal_to(expected))

    def test_not_mounted(self) -> None:
        """A mount that fails says its exit status."""
        expected = (FAILED, ["grep", "mount"])
        assert_that(line({"grep": 1, "mount": 32}), equal_to(expected))

    def test_no_proc_mounts(self) -> None:
        """Where grep finds no /proc/mounts the mount is tried, never a crash."""
        answers = {"grep": NO_MOUNTS_FILE, "mount": 1}
        expected = ("tracefs: NOT MOUNTED (mount exit status 1)", ["grep", "mount"])
        assert_that(line(answers), equal_to(expected))

    def test_programs_missing(self) -> None:
        """A machine with no grep or mount says 127, as a shell does."""
        answers = {"grep": fakes.NOT_FOUND, "mount": fakes.NOT_FOUND}
        expected = ("tracefs: NOT MOUNTED (mount exit status 127)", ["grep", "mount"])
        assert_that(line(answers), equal_to(expected))

    def test_commands(self) -> None:
        """The commands are the ones the ticket names."""
        machine = fakes.FakeProcesses(bodies={}, answers={"grep": 1, "mount": 0})
        tracefs.ensure(machine)
        expected = [
            ["grep", "tracefs", "/proc/mounts"],
            ["mount", "-t", "tracefs", "nodev", "/sys/kernel/tracing"],
        ]
        assert_that(machine.calls, equal_to(expected))


GIB = 2**30


def free(gibibytes: int) -> disk.Reader:
    """A disk with a fixed figure free, whatever the host has.

    Args:
        gibibytes: the free space.

    Returns:
        The reader of the use of a path, for every path.
    """
    return lambda _: disk.Usage(100 * GIB, (100 - gibibytes) * GIB, gibibytes * GIB)


def with_free(
    gibibytes: int, answers: fakes.Answers = fakes.TRACEFS_FOUND
) -> world.World:
    """A world whose disk has a fixed figure free.

    Args:
        gibibytes: the free space.
        answers: the exit status of the tracefs check and of the mount.

    Returns:
        The world.
    """
    return dataclasses.replace(world.make_world(answers), usage=free(gibibytes))


CASES = (
    (fakes.TRACEFS_FOUND, FOUND, False),
    ({"grep": 1, "mount": 0}, MOUNTED, True),
    ({"grep": 1, "mount": 32}, FAILED, True),
)


def run(here: world.World, command: str) -> world.Result:
    """Run one of the three commands.

    Args:
        here: the world.
        command: ``sweep``, ``pressure`` or ``slots``.

    Returns:
        What it did.
    """
    if command == "slots":
        return world.invoke(here, "slots", "show", here.config)
    return world.again(here, command, "--now", world.FUTURE)


def play(command: str) -> tuple[Sequence[tuple[str, bool]], int]:
    """Run a command in the three cases.

    Args:
        command: ``sweep``, ``pressure`` or ``slots``.

    Returns:
        For each case the first stderr line and whether the mount ran, and the
        number of different standard outputs.
    """
    played = []
    for answers, _, _ in CASES:
        here = with_free(7, answers)
        result = run(here, command)
        mount = any(call[0] == "mount" for call in here.calls)
        out = result.out.replace(str(here.workspace), "WORKSPACE")
        played.append((result.err.splitlines()[0], mount, out))
    return [(first, mount) for first, mount, _ in played], len(
        {out for _, _, out in played}
    )


class TestCommands(unittest.TestCase):
    """Sweep, pressure and slots make the mount first and say so on stderr."""

    def test_each_command(self) -> None:
        """All three lines first on stderr, and one stdout whatever they were."""
        expected = [(said, mounts) for _, said, mounts in CASES]
        found = [play(command) for command in ("sweep", "pressure", "slots")]
        assert_that(found, equal_to([(expected, 1)] * 3))

    def test_default_world_ignores_the_host_disk(self) -> None:
        """A world that gives no figure prints the fixed one, not the host's.

        The fixed figure is ``fixeddisk.fixed_usage``, 50 GiB free (pitboss#134).
        On the old default this fails unless the host has between 49.95 and
        50.05 GiB free at both reads.
        """
        out = run(world.make_world(), "sweep").out
        assert_that("disk free 50.0 GiB before, 50.0 GiB after" in out, equal_to(True))

    def test_disk_figure_is_the_injected_one(self) -> None:
        """The clean line says the injected free space, not the host's."""
        lines = []
        for gibibytes in (7, 9):
            here = with_free(gibibytes)
            lines.append(run(here, "sweep").out)
        said = [
            "disk free 7.0 GiB before, 7.0 GiB after",
            "disk free 9.0 GiB before, 9.0 GiB after",
        ]
        assert_that(
            [said[i] in out for i, out in enumerate(lines)], equal_to([True] * 2)
        )
        assert_that(said[0] in lines[1], equal_to(False))

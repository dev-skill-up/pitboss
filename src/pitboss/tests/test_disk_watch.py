"""``next`` says the free space and cleans before it suggests (pitboss#288)."""

import dataclasses
import pathlib
import tempfile
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, disk, diskwatch, machine
from . import world
from .briefmake import has_none, pinned, text
from .suggestions import next_output, parsed
from .test_brief_nox import WORKERS
from .test_plan_commands import PLAN_REVIEWS

GIBIBYTE = 2**30
TOTAL = 100 * GIBIBYTE
TEMP_RUNS = (
    "Temp files: a check that runs more than once gets its own `TMPDIR`, removed"
    " right after each run; a run that needs more than 1 GiB is left to CI"
    " (pitboss#288)."
)
NO_LOOP = (
    "Repeated runs: a Plan whose evidence is a repeated local run (a loop of N"
    " runs of a check) is a long run, which CI is the evidence for; it is changes"
    " needed, and the finding is `move the evidence to CI` (pitboss#288)."
)


def used(percent: float) -> world.World:
    """A world whose disk is a given percent used, of 100 GiB.

    Args:
        percent: how much is used.

    Returns:
        The world, whose fake ``statvfs`` answers that at every path.
    """
    free = int(TOTAL * (100 - percent) / 100)
    usage = disk.Usage(TOTAL, TOTAL - free, free)
    return dataclasses.replace(world.make_world(), usage=lambda _: usage)


def headers(output: str) -> Sequence[str]:
    """The suggestion headers of an output.

    Args:
        output: what ``slots next`` printed.

    Returns:
        The headers, in order.
    """
    return [header for header, _ in parsed(output)]


class TestDiskLine(unittest.TestCase):
    """The ``DISK`` line, the warning at 85 % and the suggestion at 90 %."""

    def test_the_line_is_always_there(self) -> None:
        """Half used: the line, no warning, no clean suggestion."""
        out = next_output(used(50))
        assert_that(out, contains_string("DISK "))
        assert_that(out, contains_string("50.0 GiB free of 100.0 GiB (50.0% used)"))
        assert_that("clean the disk" in out, equal_to(False))
        assert_that("clean before it fills" in out, equal_to(False))

    def test_an_unreadable_volume_says_nothing(self) -> None:
        """No line and no clean suggestion; the workers are suggested."""
        here = dataclasses.replace(world.make_world(), usage=lambda _: None)
        out = next_output(here)
        assert_that("DISK " in out, equal_to(False))
        assert_that(len(headers(out)), equal_to(3))

    def test_at_85_percent_the_line_warns(self) -> None:
        """The line says to clean, and no suggestion is added yet."""
        out = next_output(used(86))
        assert_that(out, contains_string("clean before it fills"))
        assert_that("clean the disk" in out, equal_to(False))

    def test_at_95_percent_cleaning_is_the_first_suggestion(self) -> None:
        """Before any worker suggestion, with the commands in order."""
        out = next_output(used(95))
        found = headers(out)
        assert_that(
            [found[0][:33], found[1][:26]],
            equal_to(
                ["SUGGESTION 1 of 4: clean the disk", "SUGGESTION 2 of 4: resolve"]
            ),
        )
        assert_that(len(found), equal_to(4))
        brief_of_first = parsed(out)[0][1]
        assert_that(brief_of_first[1], equal_to(f"1. {diskwatch.CLEAN_WORKTREES}"))
        assert_that(brief_of_first[2], equal_to(f"2. {diskwatch.CLEAN_CONTAINER}"))

    def test_at_99_9_percent_no_worker_is_suggested(self) -> None:
        """Under 1 GiB free: the clean suggestion and no worker."""
        out = next_output(used(99.9))
        assert_that(
            [each[:33] for each in headers(out)],
            equal_to(["SUGGESTION 1 of 1: clean the disk"]),
        )
        assert_that(out, contains_string("no worker starts until the disk is cleaned"))
        assert_that("SUGGESTION 2" in out, equal_to(False))


class TestLargest(unittest.TestCase):
    """The five largest entries under the scratch directories."""

    def test_the_five_largest_come_first(self) -> None:
        """Seven entries under two roots: five are kept, largest first."""
        with tempfile.TemporaryDirectory() as root:
            for number in range(1, 8):
                (pathlib.Path(root) / f"entry{number}").write_bytes(
                    b"x" * number * 65536
                )
            found = diskwatch.largest(machine.real(), [pathlib.Path(root)])
        assert_that(
            [one.path.name for one in found],
            equal_to([f"entry{number}" for number in range(7, 2, -1)]),
        )


class TestBriefs(unittest.TestCase):
    """The worker brief and the Plan-review brief carry the rules."""

    def test_every_worker_brief_has_the_temp_files_line(self) -> None:
        """One line, pinned."""
        for kind in WORKERS:
            pinned(kind, [TEMP_RUNS])
        has_none(text(brief.Kind.REVIEW_EXECUTION), [TEMP_RUNS, NO_LOOP])

    def test_a_plan_review_refuses_a_repeated_local_run(self) -> None:
        """The finding is `move the evidence to CI`."""
        for kind in PLAN_REVIEWS:
            pinned(kind, [NO_LOOP])

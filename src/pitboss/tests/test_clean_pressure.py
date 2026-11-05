"""End-to-end tests of the root files and of the disk pressure line."""

import pathlib
import unittest

from .. import account, autoclean, dead, diskline, machine
from . import cleanworld, test_tracefs, world

LATER = ("--now", world.FUTURE)


class TestRootFiles(unittest.TestCase):
    """Files in the container's root written after it started."""

    def test_root_files_are_dead_paths(self) -> None:
        """A file written well after the marker is listed; a live one is not."""
        root = cleanworld.session_root("written", "shared")
        here = world.make_world()
        cleanworld.configure(here, root)
        arguments = ("--marker", str(root / "marker"), "--root", str(root))
        out = world.again(here, "clean-container", *arguments).out
        pieces = [f"REMOVED PATH {root / 'written'}", "written over 1 hours after"]
        cleanworld.same(cleanworld.absent(out, pieces), [])
        cleanworld.same(f"{root / 'shared'}" in out, False)


class TestPressure(unittest.TestCase):
    """The warning of a sweep."""

    def test_pressure_names_the_pass_it_started_and_what_it_freed(self) -> None:
        """Under the minimum a sweep cleans hard and the line says so."""
        here = world.make_world()
        cleanworld.crowd(here, "1e9")
        late = world.again(here, "sweep", *LATER).out
        pieces = [
            f"DISK PRESSURE {here.workspace}:",
            "the aggressive clean started",
            "freed ",
            "(worktrees ",
            "clean: DISK UNDER 1e+09 GiB FREE",
            "still ",
            "no kept directory is over 500 MB",
        ]
        busy = world.again(here, "sweep").out
        cleanworld.same(
            (cleanworld.absent(late, pieces), "merged-work" in busy), ([], False)
        )

    def test_a_directory_over_500_mb_that_was_kept_is_named_with_why(self) -> None:
        """Still short of free space afterwards: each big kept directory, with why."""
        big = pathlib.Path("/w/big")
        told = account.Account(
            dry=False,
            hot=[],
            percent=90,
            freed=[2**30, 0, 0, 0],
            kept=[dead.Kept(path=big, why="its branch has an open PR", size=2**30)],
            tied=[],
            measure=lambda path: 0,
        )
        short = machine.Crowded(place=big.parent, percent=99, free=2**30, short=True)
        report = autoclean.Report(lines=[], told=told, short=[short], left=[short])
        text = "\n".join(diskline.lines(report, 5.0))
        cleanworld.same(
            cleanworld.absent(
                text,
                [
                    "DISK PRESSURE /w: 1.0 GiB free, under 5 GiB: the aggressive clean",
                    "freed 1.0 GiB (worktrees 1.0 GiB, checkouts 0.0 MiB,",
                    "DISK PRESSURE /w: still 1.0 GiB free, under 5 GiB",
                    f"  1.0 GiB {big} (its branch has an open PR)",
                ],
            ),
            [],
        )

    def test_enough_freed_says_no_more(self) -> None:
        """A file system that is no longer short has only the pass line."""
        told = account.Account(
            dry=True, hot=[], percent=90, freed=[0, 0, 0, 0], kept=[], tied=[],
            measure=lambda path: 0,
        )
        short = machine.Crowded(place=pathlib.Path("/w"), percent=99, short=True)
        report = autoclean.Report(lines=[], told=told, short=[short], left=[])
        text = diskline.lines(report, 5.0)
        cleanworld.same(
            (len(text), "would be freed 0.0 MiB" in text[0]), (1, True)
        )

    def test_no_pressure_no_line(self) -> None:
        """With room there is no line and nothing is scanned."""
        out = world.again(world.make_world(), "sweep", *LATER).out
        cleanworld.same("DISK PRESSURE" in out, False)

    def test_the_pressure_line_says_the_injected_figure(self) -> None:
        """Under the minimum the line has the injected figure; over it, none."""
        said = []
        for gibibytes in (1, 9):
            here = test_tracefs.with_free(gibibytes)
            cleanworld.crowd(here, "5")
            said.append(world.again(here, "sweep", *LATER).out)
        line = "free, under 5 GiB"
        cleanworld.same(
            ("1.0 GiB " + line in said[0], "DISK PRESSURE" in said[1]),
            (True, False),
        )

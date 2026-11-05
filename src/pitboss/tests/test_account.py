"""What the aggressive clean says it freed and kept (pitboss#194)."""

import dataclasses
import pathlib
import unittest
from typing import Sequence

from .. import account, dead, disk, local, machine
from .autocleanworld import GIB
from .cleanworld import same

MEBI = 2**20
ROOT = pathlib.Path("/w")
UNMEASURED = pathlib.Path("/w/unmeasured")
SIZES = {UNMEASURED: 900 * MEBI, ROOT / "pb-open": 600 * MEBI}
OPEN = local.Worktree(path=ROOT / "pb-open", branch="open", head="")


def big(name: str, size: int) -> dead.Kept:
    """A kept directory of a known size.

    Args:
        name: its name in the workspace.
        size: the bytes.

    Returns:
        The directory.
    """
    return dead.Kept(path=ROOT / name, why="r", size=size)


def told(
    over: int, freed: Sequence[int], kept: Sequence[dead.Kept] = ()
) -> account.Account:
    """The account of a clean of a file system that is ``over`` bytes too full.

    Args:
        over: the bytes to free to get under the limit; 0 for no pressure.
        freed: the bytes each kind of cleaning freed.
        kept: the directories left.

    Returns:
        The account; the worktree ``pb-open`` has an open PR.
    """
    crowded = [machine.Crowded(place=ROOT, percent=95, over=over)] if over else []
    return account.Account(
        dry=False,
        hot=crowded,
        percent=90,
        freed=freed,
        kept=kept,
        tied=[OPEN],
        measure=SIZES.__getitem__,
    )


class TestLines(unittest.TestCase):
    """The lines under pressure."""

    def test_no_pressure_no_account(self) -> None:
        """Below the pressure there is no such line."""
        same(account.lines(told(0, [0, 0, 0, 0])), [])

    def test_enough_freed_says_only_the_bytes_of_each_kind(self) -> None:
        """Freeing what was needed prints the kinds and no listing."""
        same(
            account.lines(told(3 * GIB, [3 * GIB, 0, 0, 0], [big("x", 2 * GIB)])),
            [
                "clean: freed by kind: worktrees 3.0 GiB, checkouts 0.0 MiB,"
                " test tempdirs 0.0 MiB, package caches 0.0 MiB"
            ],
        )

    def test_a_shortfall_names_each_kept_directory_over_500_mb(self) -> None:
        """Each big kept directory is named with why, largest first."""
        kept = [
            big("small", 100 * MEBI),
            big("pb-1", 1300 * MEBI),
            dead.Kept(path=UNMEASURED, why="holds a marker"),
            big("pb-2", 2 * GIB),
        ]
        lines = account.lines(told(10 * GIB, [GIB, 0, 0, 0], kept))
        same(
            lines[1:],
            [
                "clean: 1.0 GiB freed, 9.0 GiB short of the 10.0 GiB needed to get"
                " under 90%: each directory over 500 MB that was kept",
                "clean: kept 2.0 GiB /w/pb-2 (r): over 500 MB",
                "clean: kept 1.3 GiB /w/pb-1 (r): over 500 MB",
                "clean: kept 900.0 MiB /w/unmeasured (holds a marker): over 500 MB",
                "clean: kept 600.0 MiB /w/pb-open (open PR): over 500 MB",
            ],
        )

    def test_a_dry_run_says_would_be_freed(self) -> None:
        """The verb follows the mode."""
        dry = dataclasses.replace(told(GIB, [GIB, 0, 0, 0]), dry=True)
        same(account.lines(dry)[0].startswith("clean: would be freed by kind:"), True)


class TestDirectories(unittest.TestCase):
    """The directories left, as the account names them."""

    def test_the_registered_worktrees_are_the_worktree_parts(self) -> None:
        """A registered worktree is not named; an unsafe dead path is; in order."""
        unsafe = dead.Candidate(
            path=ROOT / "b-unsafe", size=7, reason="its PR merged", kept="1 commits"
        )
        safe = dead.Candidate(path=ROOT / "a-safe", size=9, reason="its PR merged")
        kept = [big("c-kept", 3), big("registered", 5)]
        left = account.directories_left(kept, [safe, unsafe], {ROOT / "registered"})
        same(
            [(each.path.name, each.why, each.size) for each in left],
            [("b-unsafe", "1 commits", 7), ("c-kept", "r", 3)],
        )

    def test_open_worktrees_are_named(self) -> None:
        """One line each, with the branch."""
        same(account.open_lines([OPEN]), ["clean: kept /w/pb-open [open] (open PR)"])


class TestCrowd(unittest.TestCase):
    """The bytes to free to get under the limit."""

    def test_the_bytes_over_the_limit(self) -> None:
        """A 95% full file system of 100 GiB is 5 GiB over a 90% limit."""
        usage = disk.Usage(total=100 * GIB, used=95 * GIB, free=5 * GIB)
        over = machine.crowd(ROOT, usage, 90).over
        same(5 * GIB <= over <= 5 * GIB + 2, True)

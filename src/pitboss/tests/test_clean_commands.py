"""End-to-end tests of ``clean-container`` and of the disk pressure line of a sweep."""

import os
import pathlib
import unittest
from typing import Sequence

from . import fakes, world
from .cleanworld import (
    NO_MARKER,
    absent,
    crowd,
    full_world,
    lines_of,
    same,
)

SAFE = ("merged-work", "base-work", "lib", "other-work", "old", "untracked")
KEPT = ("holder", "dirty", "broken")
LEFT_SCRATCH = ("fresh", "marked", "shared", "holder2", "link")
LEFT_WORKSPACE = ("pinned-work", "open-work", "project")
DRY = (
    "(its PR merged) (dry run",
    "(its PR was closed) (dry run",
    "(its tip is in the base branch) (dry run",
    "1 commits on no remote branch in",
    "1 changed tracked files in",
    "fetch failed in",
    "would be freed; 3 kept",
)


def clean(here: world.World, *arguments: str) -> world.Result:
    """Run ``clean-container``.

    Args:
        here: the world.
        *arguments: more arguments.

    Returns:
        What it did.
    """
    return world.again(here, "clean-container", *NO_MARKER, *arguments)


def names(paths: Sequence[str]) -> Sequence[str]:
    """The last part of each path.

    Args:
        paths: the paths.

    Returns:
        The names.
    """
    return sorted(pathlib.Path(path).name for path in paths)


class TestDryRun(unittest.TestCase):
    """The list the orchestrator approves."""

    def test_dry_run_lists_and_removes_nothing(self) -> None:
        """Dead safe paths, with sizes and reasons, and the kept ones apart."""
        here, root = full_world()
        result = clean(here)
        removed = lines_of(result.out, "REMOVED PATH")
        kept = lines_of(result.out, "KEPT PATH")
        untouched = all(pathlib.Path(path).exists() for path in removed)
        same(
            (names(removed), names(kept), untouched, absent(result.out, DRY)),
            (sorted(SAFE), sorted(KEPT), True, []),
        )
        same(f"git cannot read {root}/broken" in result.out, True)


class TestRemoval(unittest.TestCase):
    """The sweep that frees the space."""

    def test_removes_only_the_safe_list_in_parts(self) -> None:
        """Safe paths go, ``rm`` gets at most batch paths, the rest is untouched."""
        here, root = full_world()
        listed = lines_of(clean(here).out, "REMOVED PATH")
        result = clean(here, "--no-dry-run", "--batch", "2")
        removed = lines_of(result.out, "REMOVED PATH")
        calls = [call for call in here.calls if call[0] == "rm"]
        listing = fakes.run_git(here.clone, "worktree", "list")
        parts = [len(call) - 3 for call in calls]
        gone = [pathlib.Path(path).exists() for path in removed]
        same((removed, gone), (listed, [False] * len(removed)))
        same((max(parts), len(calls)), (2, (len(removed) + 1) // 2))
        same("merged-work" in listing, False)
        left = [
            *(root / name for name in (*LEFT_SCRATCH, *KEPT)),
            *(here.workspace / name for name in LEFT_WORKSPACE),
            root.parent / "locked" / "entry",
        ]
        same([each.exists() or each.is_symlink() for each in left], [True] * len(left))
        same(absent(result.out, [" freed; 3 kept", "disk: "]), [])

    def test_approved_list_limits_the_removal(self) -> None:
        """Only approved safe paths go; an unsafe or unknown one is refused."""
        here, root = full_world()
        approved = fakes.directory() / "approved"
        merged = here.workspace / "merged-work"
        unknown = here.workspace / "unknown"
        approved.write_text(f"{merged}\n{root / 'holder'}\n{unknown}\n")
        result = clean(here, "--no-dry-run", "--approved", str(approved))
        refused = sorted([str(root / "holder"), str(unknown)])
        same(lines_of(result.out, "REMOVED PATH"), [str(merged)])
        same(lines_of(result.out, "COULD NOT REMOVE PATH"), refused)
        same((root / "old").exists(), True)


class TestRootFiles(unittest.TestCase):
    """Files in the container's root written after it started."""

    def test_root_files_are_dead_paths(self) -> None:
        """A file written well after the marker is listed with the other dead paths."""
        root = fakes.directory()
        for name in ("marker", "written"):
            fakes.write(root / name, name)
        os.utime(root / "marker", (1, 1))
        arguments = ("--marker", str(root / "marker"), "--root", str(root))
        out = world.again(world.make_world(), "clean-container", *arguments).out
        pieces = [f"REMOVED PATH {root / 'written'}", "written over 1 hours after"]
        same(absent(out, pieces), [])


LATER = ("--now", world.FUTURE)


class TestPressure(unittest.TestCase):
    """The warning of a sweep."""

    def test_pressure_names_the_largest_dead_paths(self) -> None:
        """Under the minimum a sweep names the dead paths that could be freed."""
        here = world.make_world()
        crowd(here, "1e9")
        late = world.again(here, "sweep", *LATER).out
        pieces = [f"DISK PRESSURE {here.workspace}:", "merged-work (its PR merged)"]
        busy = world.again(here, "sweep").out
        same((absent(late, pieces), absent(busy, ["  no dead path found"])), ([], []))

    def test_no_pressure_no_line(self) -> None:
        """With room there is no line and nothing is scanned."""
        out = world.again(world.make_world(), "sweep", *LATER).out
        same("DISK PRESSURE" in out, False)

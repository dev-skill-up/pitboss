"""The merge step removes a merged ticket's worktree and prints bytes (merge-step)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, world
from .test_autoclean_world import OPEN, places, pull, remaining, scene
from .test_slot_commands import next_result

REMOVED = "REMOVED WORKTREE"
STALE = "STALE WORKTREE"
FINISHED = world.project_page("pulls?state=all")


def nothing(here: world.World) -> None:
    """Leave the scene as it is: ``merged-work`` is clean and its PR merged.

    Args:
        here: the world.
    """


def marker(here: world.World) -> None:
    """Leave the marker of a worker that is done.

    Args:
        here: the world.
    """
    fakes.write(places(here)["merged-work"] / ".pitboss-live", "")


def untracked(here: world.World) -> None:
    """Leave a file git does not track.

    Args:
        here: the world.
    """
    fakes.write(places(here)["merged-work"] / "scratch.txt", "x")


def closed(here: world.World) -> None:
    """Close the PR of the worktree without merging it.

    Args:
        here: the world.
    """
    here.bodies[FINISHED] = [pull("merged-work", {"state": "closed"})]


def locked(here: world.World) -> None:
    """Lock the worktree, so that git refuses to remove it.

    Args:
        here: the world.
    """
    fakes.run_git(here.clone, "worktree", "lock", str(places(here)["merged-work"]))


CASES = (
    ("merged and clean", nothing, REMOVED, ("merged-work", "merge step"), False),
    ("a done worker's marker", marker, REMOVED, ("merged-work",), False),
    ("untracked files", untracked, STALE, ("untracked", "MiB"), True),
    ("locked", locked, STALE, ("merged-work", "clean-worktrees"), True),
    ("closed", closed, STALE, ("its PR was closed", "clean-worktrees"), True),
)


def stepped(here: world.World, word: str) -> Sequence[str]:
    """Run ``slots next`` once and take the lines that hold a word.

    Args:
        here: the world, whose ``merged-work`` worktree is the ticket's.
        word: the word.

    Returns:
        The lines.
    """
    return [each for each in next_result(here).out.splitlines() if word in each]


class TestMergeStep(unittest.TestCase):
    """What ``slots next`` does about a finished worktree."""

    def test_the_bytes_are_printed(self) -> None:
        """The worktree is removed and the total says the bytes freed."""
        here = scene("100")
        out = next_result(here).out
        assert_that(out, contains_string("worktrees: 1 removed, "))
        assert_that(out, contains_string(" freed"))
        assert_that("merged-work" in remaining(here), equal_to(False))
        assert_that("open-work" in remaining(here), equal_to(True))

    def test_each_case(self) -> None:
        """Merged, merged with a done worker's marker, untracked files, closed."""
        for name, prepare, mark, parts, stays in CASES:
            with self.subTest(name):
                here = scene("100")
                prepare(here)
                lines = stepped(here, mark)
                assert_that(len(lines), equal_to(1))
                for word in parts:
                    assert_that(lines[0], contains_string(word))
                assert_that("merged-work" in remaining(here), equal_to(stays))

    def test_nothing_finished_prints_nothing(self) -> None:
        """No line of the step when no worktree is finished."""
        here = scene("100")
        here.bodies[FINISHED] = [pull("merged-work", OPEN)]
        assert_that(stepped(here, "worktrees:"), equal_to([]))

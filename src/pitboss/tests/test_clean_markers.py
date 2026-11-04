"""End-to-end tests of the live markers of merged worktrees under disk pressure."""

import unittest
from typing import Sequence

from .. import mergetime
from . import cleanworld, fakes, test_autoclean_world, world

same = cleanworld.same
NAMES = ("stale-live", "merged-old", "merged-last", "closed-live")
IGNORED = "its .pitboss-live marker is ignored: a worktree merged after it"


def scene(percent: str) -> world.World:
    """A world with four worktrees, each holding a live marker.

    ``stale-live`` has no PR and its tip is in the base branch, ``merged-old``
    is a PR merged in March, ``merged-last`` one merged in October and
    ``closed-live`` one closed without merging.

    Args:
        percent: the TOML number of ``pressure_percent``.

    Returns:
        The world; every worktree is 99 hours old.
    """
    here = world.make_world()
    cleanworld.rewrite(
        here, f"min_free_gib = 0\ntmp_roots = []\npressure_percent = {percent}\n"
    )
    for name in NAMES:
        path = fakes.add_worktree(here.clone, name)
        cleanworld.mark_live(path)
        test_autoclean_world.touch_all(path, 99)
    merged = "merged_at"
    pulls = [
        test_autoclean_world.pull("merged-old", {"state": "closed", merged: MARCH}),
        test_autoclean_world.pull("merged-last", {"state": "closed", merged: OCTOBER}),
        test_autoclean_world.pull("closed-live", {"state": "closed"}),
    ]
    here.bodies[world.project_page("pulls?state=all")] = pulls
    return here


MARCH = "2026-03-01T00:00:00Z"
# After the fixture's own commits, which are dated when the test runs.
OCTOBER = "2099-10-01T00:00:00Z"


def sweep(here: world.World) -> str:
    """Sweep at the test's now.

    Args:
        here: the world.

    Returns:
        What it printed.
    """
    return world.again(here, "sweep", *test_autoclean_world.AFTER).out


def on_disk(here: world.World) -> Sequence[bool]:
    """Whether each worktree of the scene is still there.

    Args:
        here: the world.

    Returns:
        One answer for each, in the order of ``NAMES``.
    """
    return [(here.workspace / name).exists() for name in NAMES]


class TestMarkersUnderPressure(unittest.TestCase):
    """The aggressive clean does not honor the marker of a merged worktree."""

    def test_the_older_merged_worktrees_go_and_the_last_merged_stays(self) -> None:
        """A marker saves only the worktree whose PR merged last; the line names it."""
        here = scene("0.001")
        out = sweep(here)
        root = here.workspace
        same(on_disk(here), [False, False, True, True])
        test_autoclean_world.shows(
            out,
            [
                "clean: DISK OVER 0.001%",
                f"REMOVED WORKTREE {root}/stale-live"
                f" (its tip is in the base branch; {IGNORED})",
                f"REMOVED WORKTREE {root}/merged-old (its PR merged; {IGNORED})",
                f"KEPT WORKTREE {root}/merged-last"
                " (holds a file named .pitboss-live; its PR merged last)",
                f"KEPT WORKTREE {root}/closed-live (holds a file named .pitboss-live)",
            ],
        )

    def test_with_room_on_the_disk_every_marker_is_honored(self) -> None:
        """Below the pressure the marker is absolute, as it was."""
        here = scene("99.9")
        out = sweep(here)
        same(on_disk(here), [True] * 4)
        same(out.count("holds a file named .pitboss-live)"), 4)


class TestSeconds(unittest.TestCase):
    """Reading a merge time."""

    def test_a_time_is_read_and_a_word_is_the_oldest(self) -> None:
        """An ISO 8601 time is seconds; anything else is 0."""
        same(
            (
                mergetime.seconds(MARCH) < mergetime.seconds(OCTOBER),
                mergetime.seconds("x"),
            ),
            (True, 0.0),
        )

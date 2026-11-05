"""End-to-end tests of the live markers of merged worktrees under disk pressure."""

import unittest
from typing import Sequence

from .. import mergetime
from . import cleanruns, cleanworld, fakes, test_autoclean_world, world

same = cleanworld.same
NAMES = ("stale-live", "merged-old", "merged-last", "closed-live")
IGNORED = "its .pitboss-live marker is ignored: a worktree merged after it"


MARCH = "2026-03-01T00:00:00Z"
# After the fixture's own commits, which are dated when the test runs.
OCTOBER = "2099-10-01T00:00:00Z"


def pulls() -> Sequence[object]:
    """What GitHub says of the scene's branches.

    Returns:
        The pull requests: two merged and one closed.
    """
    closed = {"state": "closed"}
    return [
        test_autoclean_world.pull("merged-old", {**closed, "merged_at": MARCH}),
        test_autoclean_world.pull("merged-last", {**closed, "merged_at": OCTOBER}),
        test_autoclean_world.pull("closed-live", closed),
    ]


def scene(percent: str, marker_hours: float = 4) -> world.World:
    """A world with four worktrees, each holding a live marker.

    ``stale-live`` has no PR and its tip is in the base branch, ``merged-old``
    is a PR merged in March, ``merged-last`` one merged in October and
    ``closed-live`` one closed without merging.

    Args:
        percent: the TOML number of ``pressure_percent``.
        marker_hours: how old each marker is (the default is older than the
            idle hours and younger than a worker's task).

    Returns:
        The world; every worktree but its marker is 99 hours old.
    """
    here = world.make_world()
    settings = f"min_free_gib = 0\ntmp_roots = []\npressure_percent = {percent}\n"
    cleanworld.rewrite(here, settings)
    for name in NAMES:
        path = fakes.add_worktree(here.clone, name)
        test_autoclean_world.touch_all(path, 99)
        cleanworld.mark_live_since(path, marker_hours, world.START.timestamp())
    here.bodies[world.project_page("pulls?state=all")] = pulls()
    return here


def sweep(here: world.World) -> str:
    """Sweep at the test's now.

    Args:
        here: the world.

    Returns:
        What it printed.
    """
    return world.again(here, "sweep", *test_autoclean_world.AFTER).out


class TestMarkersUnderPressure(unittest.TestCase):
    """The aggressive clean does not honor the marker of a merged worktree."""

    def test_the_older_merged_worktrees_go_and_the_last_merged_stays(self) -> None:
        """A marker saves only the worktree whose PR merged last; the line names it."""
        here = scene("0.001")
        out = sweep(here)
        root = here.workspace
        same(cleanruns.present(here, NAMES), [False, False, True, True])
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

    def test_with_room_on_the_disk_every_young_marker_is_honored(self) -> None:
        """Below the pressure a marker within a worker's task (6 hours) is absolute."""
        for hours in (4, 5):
            here = scene("99.9", marker_hours=hours)
            out = sweep(here)
            same(cleanruns.present(here, NAMES), [True] * 4)
            same(out.count("holds a file named .pitboss-live)"), 4)


class TestOldMarkers(unittest.TestCase):
    """A marker older than a worker's task saves no merged worktree (pitboss#194)."""

    def test_a_merged_worktree_with_an_old_marker_goes_even_with_room(self) -> None:
        """The last merged one too; a closed one keeps the marker it holds."""
        here = scene("99.9", marker_hours=7)
        out = sweep(here)
        root = here.workspace
        old = (
            "its .pitboss-live marker is older than 6 hours, longer than a worker runs"
        )
        same(cleanruns.present(here, NAMES), [False, False, False, True])
        test_autoclean_world.shows(
            out,
            [
                f"REMOVED WORKTREE {root}/stale-live"
                f" (its tip is in the base branch; {old})",
                f"REMOVED WORKTREE {root}/merged-old (its PR merged; {old})",
                f"REMOVED WORKTREE {root}/merged-last (its PR merged; {old})",
                f"KEPT WORKTREE {root}/closed-live (holds a file named .pitboss-live)",
            ],
        )


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

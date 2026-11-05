"""A sweep under disk pressure cleans the workspace of every repository (pitboss#205).

The workspace holds directories of the configured repository and of one the
configuration does not name; the disk is nearly full by either rule (over the
percent used, or under the minimum free space) and the merged ones go, the ones
with an open PR stay, whatever repository the sweep's configuration is for.
"""

import dataclasses
import unittest

from .. import disk
from . import cleanruns, cleanworld, fakes, test_autoclean_world, test_clean_clones
from . import world

same = cleanworld.same
shows = test_autoclean_world.shows
GIB = 2**30
FOREIGN = test_clean_clones.FOREIGN
NAMES = ("merged-work", "open-work", "foreign-merged", "foreign-open")
SETTINGS = "min_free_gib = 5\ntmp_roots = []\npressure_percent = 90\n"


def two_repositories(usage: disk.Usage) -> world.World:
    """A workspace of two repositories, on a disk of a given use.

    ``merged-work`` and ``open-work`` are worktrees of the configured
    repository, ``foreign-merged`` and ``foreign-open`` clones of another one;
    the PR of each ``merged`` branch merged, the PR of each ``open`` one is open.

    Args:
        usage: the use of the disk.

    Returns:
        The world; everything in the workspace is 99 hours old.
    """
    here = dataclasses.replace(world.make_world(), usage=lambda _: usage)
    opened = fakes.add_worktree(here.clone, "open-work")
    fakes.commit_file(opened, "open-work")
    fakes.push(opened)
    for name in ("foreign-merged", "foreign-open"):
        test_clean_clones.foreign_clone(here, name, name)
    here.bodies[world.project_page("pulls?state=all")] = [
        test_autoclean_world.pull("merged-work", test_clean_clones.MERGED),
        test_autoclean_world.pull("open-work", test_clean_clones.OPEN),
    ]
    here.bodies[fakes.page(f"repos/{FOREIGN}/pulls?state=all")] = [
        test_autoclean_world.pull("foreign-merged", test_clean_clones.MERGED),
        test_autoclean_world.pull("foreign-open", test_clean_clones.OPEN),
    ]
    cleanworld.rewrite(here, SETTINGS)
    for name in NAMES:
        test_autoclean_world.touch_all(here.workspace / name, 99)
    return here


class TestTwoRepositories(unittest.TestCase):
    """The merged directories of both repositories go, the open ones stay."""

    def test_98_percent_used_and_1_gib_free(self) -> None:
        """Both rules hold: the merged go, the open stay, the line says so."""
        here = two_repositories(disk.Usage(50 * GIB, 49 * GIB, GIB))
        out = test_autoclean_world.swept(here, "sweep")
        same(cleanruns.present(here, NAMES), [False, True, False, True])
        shows(
            out,
            [
                "clean: DISK OVER 90%",
                f"REMOVED WORKTREE {here.workspace}/merged-work (its PR merged)",
                f"REMOVED PATH {here.workspace}/foreign-merged",
                f"DISK PRESSURE {here.workspace}: 1.0 GiB free, under 5 GiB:",
                "the aggressive clean started",
                "freed ",
                f"DISK PRESSURE {here.workspace}: still 1.0 GiB free, under 5 GiB",
            ],
        )

    def test_under_5_gib_free_alone_starts_the_aggressive_pass(self) -> None:
        """85 percent used is under the limit; 1 GiB free is not enough."""
        here = two_repositories(disk.Usage(7 * GIB, 6 * GIB, GIB))
        out = test_autoclean_world.swept(here, "sweep")
        same(cleanruns.present(here, NAMES), [False, True, False, True])
        shows(
            out,
            [
                "clean: DISK UNDER 5 GiB FREE",
                f"{here.workspace} 86%, 1.0 GiB free",
                f"REMOVED PATH {here.workspace}/foreign-merged",
                "the aggressive clean started",
            ],
        )

    def test_a_directory_whose_pull_requests_cannot_be_read_is_kept(self) -> None:
        """Its repository is not read: the directory stays, with the reason."""
        here = two_repositories(disk.Usage(50 * GIB, 49 * GIB, GIB))
        test_clean_clones.foreign_clone(
            here, "foreign-unread", "foreign-unread", test_clean_clones.HIDDEN
        )
        test_autoclean_world.touch_all(here.workspace / "foreign-unread", 99)
        out = test_autoclean_world.swept(here, "sweep")
        same(cleanruns.present(here, ["foreign-unread"]), [True])
        shows(
            out,
            [
                f"clean: kept {here.workspace}/foreign-unread"
                f" (the PRs of {test_clean_clones.HIDDEN} could not be read)"
            ],
        )

    def test_with_room_the_pressure_rules_do_not_start(self) -> None:
        """10 GiB free of 50 is neither over 90 percent nor under 5 GiB."""
        here = two_repositories(disk.Usage(50 * GIB, 40 * GIB, 10 * GIB))
        out = test_autoclean_world.swept(here, "sweep")
        same("DISK PRESSURE" in out or "aggressive" in out, False)

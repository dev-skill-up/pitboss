"""A sweep under disk pressure cleans the workspace of every repository (pitboss#205).

The workspace holds directories of the configured repository and of one the
configuration does not name; the disk is nearly full by either rule (over the
percent used, or under the minimum free space) and the merged ones go, the ones
with an open PR stay, whatever repository the sweep's configuration is for.
"""

import dataclasses
import unittest
from typing import Sequence

from .. import disk
from . import cleanruns, cleanworld, fakes, test_autoclean_world, test_clean_clones
from . import world, worldcopy

same = cleanworld.same
shows = test_autoclean_world.shows
GIB = 2**30
NAMES = ("merged-work", "open-work", "foreign-merged", "foreign-open")
SETTINGS = "min_free_gib = 5\ntmp_roots = []\npressure_percent = 90\n"


def figures(total: int, used: int) -> disk.Usage:
    """The use of a disk.

    Args:
        total: its size, in GiB.
        used: the GiB used.

    Returns:
        The use.
    """
    return disk.Usage(total * GIB, used * GIB, (total - used) * GIB)


FULL = figures(50, 49)
SHORT = figures(7, 6)
ROOMY = figures(50, 40)


def pulls(*branches: str) -> Sequence[object]:
    """The pull requests of a repository: ``-merged`` branches merged, others open.

    Args:
        *branches: the head branches.

    Returns:
        The page entries.
    """
    states = {True: test_clean_clones.MERGED, False: test_clean_clones.OPEN}
    return [
        test_autoclean_world.pull(name, states["merged" in name]) for name in branches
    ]


def built_scene() -> worldcopy.Made:
    """Build the world of ``two_repositories``: two repositories, 99 hours old.

    Returns:
        The world, and no directory outside its workspace.
    """
    here = world.make_world()
    opened = fakes.add_worktree(here.clone, "open-work")
    fakes.commit_file(opened, "open-work")
    fakes.push(opened)
    for name in ("foreign-merged", "foreign-open"):
        test_clean_clones.foreign_clone(here, name, name)
    foreign = f"repos/{test_clean_clones.FOREIGN}/pulls?state="
    ours = world.project_page("pulls?state=closed")
    here.bodies.update(
        {
            ours: pulls(*NAMES[:2]),
            fakes.page(f"{foreign}open"): [],
            fakes.page(f"{foreign}closed"): pulls(*NAMES[2:]),
        }
    )
    cleanworld.rewrite(here, SETTINGS)
    for name in NAMES:
        test_autoclean_world.touch_all(here.workspace / name, 99)
    return here, []


scene_template = worldcopy.cached(built_scene)


def two_repositories(usage: disk.Usage) -> world.World:
    """A copy of a workspace of two repositories, on a disk of a given use.

    ``merged-work`` and ``open-work`` are worktrees of the configured
    repository, ``foreign-merged`` and ``foreign-open`` clones of another one.

    Args:
        usage: the use of the disk.

    Returns:
        The world; everything in the workspace is 99 hours old.
    """
    here = worldcopy.copy_of(scene_template())[0]
    return dataclasses.replace(here, usage=lambda _: usage)


def swept(usage: disk.Usage) -> tuple[world.World, str]:
    """Sweep a workspace of two repositories.

    Args:
        usage: the use of the disk.

    Returns:
        The world and what the sweep printed.
    """
    here = two_repositories(usage)
    return here, test_autoclean_world.swept(here, "sweep")


class TestTwoRepositories(unittest.TestCase):
    """The merged directories of both repositories go, the open ones stay."""

    def test_98_percent_used_and_1_gib_free(self) -> None:
        """Both rules hold: the merged go, the open stay, the line says so."""
        here, out = swept(FULL)
        root = here.workspace
        kept = cleanruns.present(here, NAMES)
        shows(
            out,
            [
                "clean: DISK OVER 90%",
                f"REMOVED WORKTREE {root}/merged-work (its PR merged)",
                f"REMOVED PATH {root}/foreign-merged",
                f"DISK PRESSURE {root}: 1.0 GiB free, under 5 GiB:",
                "the aggressive clean started",
                "freed ",
                f"DISK PRESSURE {root}: still 1.0 GiB free, under 5 GiB",
            ],
        )
        same(kept, [False, True, False, True])

    def test_under_5_gib_free_alone_starts_the_aggressive_pass(self) -> None:
        """86 percent used is under the limit; 1 GiB free is not enough."""
        here, out = swept(SHORT)
        kept = cleanruns.present(here, NAMES)
        said = ["clean: DISK UNDER 5 GiB FREE", "the aggressive clean started"]
        shows(out, [*said, f"{here.workspace} 86%, 1.0 GiB free"])
        same(kept, [False, True, False, True])

    def test_86_percent_used_and_1_gib_free_names_the_free_space_rule(self) -> None:
        """The shortfall is to have 5 GiB free; 86 percent used needs no freeing."""
        out = swept(SHORT)[1]
        shows(out, [" short of the ", "needed to have 5 GiB free:"])
        same("get under 90%" in out, False)

    def test_a_directory_whose_pull_requests_cannot_be_read_is_kept(self) -> None:
        """Its repository is not read: the directory stays, with the reason."""
        here = two_repositories(FULL)
        hidden = test_clean_clones.HIDDEN
        test_clean_clones.foreign_clone(here, "foreign-unread", "unread", hidden)
        test_autoclean_world.touch_all(here.workspace / "foreign-unread", 99)
        out = test_autoclean_world.swept(here, "sweep")
        same(cleanruns.present(here, ["foreign-unread"]), [True])
        shows(
            out,
            [
                f"clean: kept {here.workspace}/foreign-unread"
                f" (the PRs of {hidden} could not be read)"
            ],
        )

    def test_with_room_the_pressure_rules_do_not_start(self) -> None:
        """10 GiB free of 50 is neither over 90 percent nor under 5 GiB."""
        out = swept(ROOMY)[1]
        same(("DISK PRESSURE" in out, "aggressive" in out), (False, False))

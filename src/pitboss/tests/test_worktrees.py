"""End-to-end tests of finished worktrees: ``auto`` removes, ``list`` lists."""

import pathlib
import unittest
from typing import Sequence

from . import cleanworld, fakes, world

AFTER = ("--now", world.FUTURE)
UNSAFE = ("unpushed-work", "changed-work", "live-work")


def scene() -> world.World:
    """A world with a finished worktree of every kind, all with a merged PR.

    ``merged-work`` is clean; ``unpushed-work`` has a commit on no remote
    branch, ``changed-work`` a changed tracked file and ``live-work`` a live
    marker.

    Returns:
        The world.
    """
    here = world.make_world()
    for name in UNSAFE:
        path = fakes.add_worktree(here.clone, name)
        fakes.commit_file(path, name)
        if name != "unpushed-work":
            fakes.push(path)
    (here.workspace / "changed-work" / "changed-work").write_text("edited")
    cleanworld.mark_live(here.workspace / "live-work")
    done = {"state": "closed", "merged_at": "x"}
    branches = ("merged-work", *UNSAFE)
    page = world.project_page("pulls?state=all")
    here.bodies[page] = [{"head": {"ref": branch}, **done} for branch in branches]
    return here


def present(here: world.World, *names: str) -> Sequence[bool]:
    """Whether each worktree is still on disk.

    Args:
        here: the world.
        *names: the worktrees.

    Returns:
        One answer for each.
    """
    return [pathlib.Path(here.workspace / name).exists() for name in names]


def left(here: world.World, cleaned: bool) -> None:
    """Assert which worktrees are on disk: all, or all but the clean one.

    Args:
        here: the world.
        cleaned: whether the clean worktree should be gone.
    """
    expected = [not cleaned, True, True, True]
    cleanworld.same(present(here, "merged-work", *UNSAFE), expected)


def sweep_shows(here: world.World, pieces: Sequence[str], *argv: str) -> None:
    """Assert that a sweep's output holds every piece.

    Args:
        here: the world.
        pieces: what it should print.
        *argv: more arguments of the sweep.
    """
    out = world.again(here, "sweep", *argv).out
    cleanworld.same(cleanworld.absent(out, pieces), [])


class TestAuto(unittest.TestCase):
    """The default: a sweep removes what the safety test passes."""

    def test_a_sweep_removes_the_clean_one_and_keeps_the_rest(self) -> None:
        """Nothing unpushed, no tracked change and no live marker is removed."""
        here = scene()
        root = here.workspace
        sweep_shows(
            here,
            [
                f"REMOVED WORKTREE {root}/merged-work (its PR merged)\n",
                f"KEPT WORKTREE {root}/unpushed-work (1 commits on no remote branch",
                f"KEPT WORKTREE {root}/changed-work (1 changed tracked files",
                f"KEPT WORKTREE {root}/live-work (holds a file named .pitboss-live)",
                "worktrees: 1 removed,",
                " freed; 3 kept",
            ],
            *AFTER,
        )
        left(here, True)

    def test_a_recent_change_keeps_a_finished_worktree(self) -> None:
        """Work done within the idle hours is in use: kept, with that reason."""
        here = scene()
        said = f"KEPT WORKTREE {here.workspace}/merged-work (changed within"
        sweep_shows(here, [f"{said} the idle hours)"])
        left(here, False)

    def test_clean_worktrees_is_judged_by_the_same_test(self) -> None:
        """The command keeps the same ones; a dry run removes none."""
        here = scene()
        dry = world.again(here, "clean-worktrees", *AFTER).out
        before = present(here, "merged-work", *UNSAFE)
        out = world.again(here, "clean-worktrees", *AFTER, "--no-dry-run").out
        said = ("(its PR merged) (dry run" in dry, "worktrees: 1 removed," in out)
        cleanworld.same((said, before), ((True, True), [True] * 4))
        left(here, True)


def listing(here: world.World) -> Sequence[object]:
    """What a sweep under ``list`` printed and left on disk.

    Args:
        here: the world.

    Returns:
        The missing wanted pieces, the missing unwanted ones, the worktree.
    """
    said = world.again(here, "sweep", *AFTER).out
    stale = f"STALE WORKTREE {here.workspace}/merged-work [merged-work]"
    wanted = [f"{stale} (its PR merged)", "worktrees: 1 stale"]
    unwanted = ["KEPT WORKTREE", "REMOVED WORKTREE"]
    absent = (cleanworld.absent(said, wanted), cleanworld.absent(said, unwanted))
    return [*absent, *present(here, "merged-work")]


class TestList(unittest.TestCase):
    """``[clean] worktrees = "list"``: today's behaviour."""

    def test_a_sweep_lists_and_removes_nothing(self) -> None:
        """Only the worktree that passes the test is listed as stale."""
        unwanted = ["KEPT WORKTREE", "REMOVED WORKTREE"]
        here = scene()
        cleanworld.only_list_worktrees(here)
        cleanworld.same(listing(here), [[], unwanted, True])

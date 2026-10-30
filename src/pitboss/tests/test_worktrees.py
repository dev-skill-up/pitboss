"""End-to-end tests of finished worktrees: ``auto`` removes, ``list`` lists."""

import dataclasses
import pathlib
import time
import unittest
from typing import Sequence

from .. import dead
from . import cleanworld, fakes, world

AFTER = ("--now", world.FUTURE)
UNSAFE = ("unpushed-work", "changed-work", "live-work", "untracked-work")
HOLDS = "is or holds the directory this command runs in"


def scene() -> world.World:
    """A world with a finished worktree of every kind, all with a merged PR.

    ``merged-work`` is clean; ``unpushed-work`` has a commit on no remote
    branch, ``changed-work`` a changed tracked file, ``live-work`` a live
    marker and ``untracked-work`` an untracked file.

    Returns:
        The world.
    """
    here = world.make_world()
    for name in UNSAFE:
        path = fakes.add_worktree(here.clone, name)
        fakes.commit_file(path, name)
        if name != "unpushed-work":
            fakes.push(path)
    files = (
        ("changed-work", "changed-work", "edited"),
        ("untracked-work", "notes", "mine"),
    )
    for name, leaf, text in files:
        (here.workspace / name / leaf).write_text(text)
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
    expected = [not cleaned, *(True for _ in UNSAFE)]
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
                f"KEPT WORKTREE {root}/untracked-work (1 untracked files: git"
                " worktree remove refuses them)",
                "worktrees: 1 removed,",
                " freed; 4 kept",
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
        cleanworld.same((said, before), ((True, True), [True] * 5))
        left(here, True)

    def test_a_sweep_keeps_the_worktree_it_runs_in(self) -> None:
        """Its own directory, and a worktree above it, are never removed."""
        here = scene()
        own = here.workspace / "merged-work"
        inside = own / "deeper"
        inside.mkdir()
        outs = [
            world.again(here, "sweep", *AFTER, directory=each).out
            for each in (own, inside)
        ]
        wanted = f"KEPT WORKTREE {own} ({HOLDS})"
        cleanworld.same([wanted in out for out in outs], [True, True])
        left(here, False)


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


class TestWorkingDirectory(unittest.TestCase):
    """The one safety test holds the directory a command runs in."""

    def test_the_directory_and_what_holds_it_are_held(self) -> None:
        """So ``clean-container`` and the disk scan keep them too."""
        top = fakes.directory()
        inside = top / "a" / "b"
        inside.mkdir(parents=True)
        (top / "other").mkdir()
        look = dataclasses.replace(cleanworld.look_in(top), working=frozenset({inside}))
        later = time.time() + 3600
        names = ("a", "a/b", "other")
        found = [dead.hold(look, top / name, later)[0] for name in names]
        cleanworld.same(found, [HOLDS, HOLDS, ""])

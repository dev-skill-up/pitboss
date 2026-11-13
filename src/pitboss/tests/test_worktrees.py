"""End-to-end tests of finished worktrees: ``auto`` removes, ``list`` lists."""

import dataclasses
import pathlib
import time
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string

from .. import dead, judging, local, worktrees
from . import cleanworld, fakes, world, worldcopy
from .fakes import write

AFTER = ("--now", world.FUTURE)
UNSAFE = ("unpushed-work", "changed-work", "live-work", "untracked-work")
DIRTY = ("unpushed-work", "changed-work", "untracked-work")
HOLDS = "is or holds the directory this command runs in"


def built_scene() -> worldcopy.Made:
    """Build the world of ``scene``, with a merged PR for every worktree.

    Returns:
        The world, and no directory outside its workspace.
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
        write(here.workspace / name / leaf, text)
    started = world.START.timestamp()
    cleanworld.mark_live_since(here.workspace / "live-work", 4, started)
    done = {"state": "closed", "merged_at": "x"}
    branches = ("merged-work", *UNSAFE)
    page = world.project_page("pulls?state=closed")
    here.bodies[page] = [{"head": {"ref": branch}, **done} for branch in branches]
    return here, []


scene_template = worldcopy.cached(built_scene)


def scene() -> world.World:
    """A copy of a world with a finished worktree of every kind, all with a merged PR.

    ``merged-work`` is clean; ``unpushed-work`` has a commit on no remote
    branch, ``changed-work`` a changed tracked file, ``live-work`` a live
    marker and ``untracked-work`` an untracked file.

    Returns:
        The world.
    """
    return worldcopy.copy_of(scene_template())[0]


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


class TestUnderDev(unittest.TestCase):
    """A worktree under /dev is never removed (#424)."""

    def test_a_worktree_under_dev_is_refused_naming_the_path(self) -> None:
        """No git worktree remove gets a path under /dev; its sibling gets one."""
        top = fakes.directory()
        look = cleanworld.look_in(top)
        run = fakes.FakeProcesses(bodies={})
        action = worktrees.Action(run=run, dry=False)

        def removed(path: pathlib.Path) -> tuple[str, bool]:
            tree = local.Worktree(path=path, branch="b", head="h")
            found = judging.Finished(worktree=tree, reason=local.Reason.MERGED)
            return worktrees.removal_line(
                action, look, judging.Judged(found=found, size=0, why="")
            )

        said = [removed(pathlib.Path(spelled)) for spelled in ("/dev/shm/x", "/dev")]
        cleanworld.same([flag for _, flag in said], [False, False])
        cleanworld.same(run.calls, [])
        for (line, _), spelled in zip(said, ("/dev/shm/x", "/dev")):
            assert_that(line, contains_string(f"{spelled} is under /dev"))
        removed(top / "dev")
        cleanworld.same([call[-1] for call in run.calls], [str(top / "dev")])


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


def merged_out(here: world.World, branch: str, *more: str) -> str:
    """Run ``pitboss merged`` for a branch.

    Args:
        here: the world.
        branch: the branch of the merged PR.
        *more: more arguments.

    Returns:
        What it printed.
    """
    return world.again(here, "merged", branch, *AFTER, *more).out


class TestMerged(unittest.TestCase):
    """The merge step removes the worktree of a merged branch at once (#471)."""

    def test_the_clean_worktree_goes_with_its_bytes_printed_and_no_force(self) -> None:
        """A dry run removes none; the real run removes it."""
        here = scene()
        dry = merged_out(here, "merged-work")
        before = present(here, "merged-work")
        out = merged_out(here, "merged-work", "--no-dry-run")
        removed = f"REMOVED WORKTREE {here.workspace}/merged-work (merged): freed "
        cleanworld.same((before, present(here, "merged-work")), ([True], [False]))
        cleanworld.same("--force" in str(here.calls), False)
        wanted = {
            dry: ["(dry run: --no-dry-run removes it)"],
            out: [removed, " bytes\n"],
        }
        cleanworld.same([cleanworld.absent(k, v) for k, v in wanted.items()], [[], []])

    def test_the_marker_of_a_merged_worktree_does_not_keep_it(self) -> None:
        """The worker is done: only the marker is untracked, and it goes."""
        here = scene()
        out = merged_out(here, "live-work", "--no-dry-run")
        cleanworld.same(
            (present(here, "live-work"), "REMOVED WORKTREE" in out), ([False], True)
        )

    def test_work_that_is_not_clean_is_kept(self) -> None:
        """A commit on no remote branch, a changed file, an untracked file."""
        here = scene()
        said = {}
        for name in DIRTY:
            said[name] = merged_out(here, name, "--no-dry-run")
        kept = {
            name: f"KEPT WORKTREE {here.workspace}/{name}" in out
            for name, out in said.items()
        }
        cleanworld.same(kept, {name: True for name in said})
        cleanworld.same(present(here, "merged-work", *DIRTY), [True] * 4)

    def test_another_branch_is_not_touched(self) -> None:
        """Nothing is listed for a branch with no worktree."""
        here = scene()
        out = merged_out(here, "no-such-branch", "--no-dry-run")
        cleanworld.same(
            ("worktrees: 0 listed, freed 0 bytes" in out, present(here, "merged-work")),
            (True, [True]),
        )

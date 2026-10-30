"""Tests for what is safe to remove: work that exists only here, and what is unseen."""

import pathlib
import subprocess
import unittest
from typing import AbstractSet

from .. import repocheck, survey
from . import cleanworld, fakes
from .cleanworld import failing, same

NOBODY: AbstractSet[pathlib.Path] = frozenset()


def verdict(path: pathlib.Path, run: fakes.Processes | None = None) -> str:
    """Why a path is not safe, by a walk of it and real git.

    Args:
        path: the path.
        run: the runner; real git by default.

    Returns:
        The reason, or empty.
    """
    use = fakes.FakeProcesses(bodies={}) if run is None else run
    return repocheck.trouble(use, path, survey.walk(path, NOBODY))


def fresh() -> pathlib.Path:
    """A clone of a new origin in a new directory.

    Returns:
        The clone.
    """
    return fakes.make_repository(fakes.directory())


def local_branch(clone: pathlib.Path, name: str) -> None:
    """Commit a file on a new local branch, then go back to main.

    Args:
        clone: the checkout.
        name: the branch.
    """
    fakes.run_git(clone, "checkout", "-qb", name)
    fakes.commit_file(clone, name)
    fakes.run_git(clone, "checkout", "-q", "main")


class TestOneCheckout(unittest.TestCase):
    """The checks of one checkout."""

    def test_trouble(self) -> None:
        """Unpushed commits, tracked changes and a broken repository each say so."""
        clone = fresh()
        clean = verdict(clone)
        (clone / "untracked").write_text("x")
        untracked = verdict(clone)
        (clone / "README").write_text("changed")
        changed = verdict(clone)
        fakes.run_git(clone, "checkout", "-q", "--", "README")
        fakes.commit_file(clone, "new")
        ahead = verdict(clone)
        broken = fakes.directory()
        (broken / ".git").mkdir()
        mute = verdict(clone, failing)
        found = (clean, untracked, changed, ahead, verdict(broken))
        same(mute, f"git cannot read {clone}")
        expected = (
            "",
            "",
            f"1 changed tracked files in {clone}",
            f"1 commits on no remote branch in {clone}",
            f"git cannot read {broken}",
        )
        same(found, expected)

    def test_a_broken_git_directory_inside_another_repository(self) -> None:
        """Git falling through to the repository above is not reading this one."""
        outer = fresh()
        (outer / "inner/.git").mkdir(parents=True)
        same(verdict(outer / "inner"), f"git cannot read {outer / 'inner'}")

    def test_a_branch_with_no_commit_has_nothing_to_lose(self) -> None:
        """HEAD of a new repository names no commit; any other failure is raised."""
        empty = fakes.directory()
        fakes.run_git(empty, "init", "-q")
        run = fakes.FakeProcesses(bodies={})
        same(
            (repocheck.has_head(run, empty), repocheck.in_head(run, empty)), (False, 0)
        )
        same(repocheck.in_every_ref(run, empty), 0)
        with self.assertRaises(subprocess.CalledProcessError):
            repocheck.has_head(run, fakes.directory())


class TestWhatTheRemovalLoses(unittest.TestCase):
    """Removing a path loses the repository that is inside it, whole."""

    def test_other_branches_and_the_stash_of_a_standalone_clone(self) -> None:
        """A branch or a stash that is on no remote is work that exists only here."""
        branch = fresh()
        local_branch(branch, "side")
        stash = fresh()
        (stash / "README").write_text("stashed")
        fakes.run_git(stash, *fakes.IDENTITY, "stash", "push", "-q")
        found = [verdict(each) for each in (branch, stash)]
        same([text.split(" ")[0] for text in found], ["1", "2"])
        same(verdict(fresh()), "")

    def test_a_linked_worktree_goes_without_its_repository(self) -> None:
        """Only the worktree's HEAD is lost; the repository elsewhere keeps its refs."""
        workspace = fakes.directory()
        main = fakes.make_repository(workspace)
        local_branch(main, "other-work")
        linked = fakes.add_worktree(main, "linked")
        same(verdict(linked), "")
        same(verdict(main).split(" ")[0], "1")
        fakes.commit_file(linked, "its-own")
        same(verdict(linked).split(" ")[0], "1")

    def test_a_clone_five_levels_down_is_judged(self) -> None:
        """A commit on no remote is found at any depth."""
        entry = fakes.directory()
        deep = entry / "a/b/c/d"
        deep.mkdir(parents=True)
        clone = fakes.make_repository(deep)
        before = verdict(entry)
        fakes.commit_file(clone, "only-here")
        same((before, verdict(entry).split(" ")[0]), ("", "1"))

    def test_a_repository_whose_directory_is_inside_the_path_is_whole(self) -> None:
        """A submodule's working tree has a .git file, and its refs live in the path."""
        super_project = fresh()
        sub_origin = fresh()
        fakes.run_git(
            super_project,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            fakes.run_git(sub_origin, "remote", "get-url", "origin").strip(),
            "sub",
        )
        fakes.run_git(super_project, *fakes.IDENTITY, "commit", "-qm", "add sub")
        fakes.push(super_project)
        sub = super_project / "sub"
        before = verdict(super_project)
        local_branch(sub, "sub-side")
        found = verdict(super_project)
        same((before, found), ("", f"1 commits on no remote branch in {sub}"))


class TestWhatIsUnseen(unittest.TestCase):
    """What a walk cannot see keeps a path."""

    def test_bare_repository_mount_and_missing_path(self) -> None:
        """Each is a reason to keep the path, with the thing named."""
        top = fakes.directory()
        cleanworld.bare_mirror(top)
        same(verdict(top), f"bare git repository {top / 'mirror.git'}")
        mount = fakes.directory()
        found = survey.walk(mount, {mount.resolve()})
        run = fakes.FakeProcesses(bodies={})
        same(repocheck.trouble(run, mount, found), f"mount point {mount}")
        gone = fakes.directory() / "gone"
        same(verdict(gone), f"cannot look at {gone}")

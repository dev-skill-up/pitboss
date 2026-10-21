"""Tests for stragglers and stale worktrees, on real git repositories."""

import os
import pathlib
import shutil
import time
import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import config, local, shapes
from . import fakes

OLD = time.time() - 10 * 3600
CUTOFF = OLD + 3600
PUSHED = ("merged", "closed", "open", "dirty", "fresh", "no-pull")
DETACHED = ("in-base", "gone")
OUTCOMES = {
    "merged": shapes.Outcome(branch="merged", still_open=False, merged=True),
    "closed": shapes.Outcome(branch="closed", still_open=False, merged=False),
    "open": shapes.Outcome(branch="open", still_open=True, merged=False),
}
STALE = {
    "merged": local.Reason.MERGED,
    "closed": local.Reason.CLOSED,
    "in-base": local.Reason.IN_BASE,
}
ALL_PULLS = fakes.page("repos/o/r/pulls?state=all")
TWO_PULLS = [
    {"head": {"ref": "b"}, "state": "open"},
    {"head": {"ref": "b"}, "state": "closed", "merged_at": "x"},
]


UNCOMMITTED = {"dirty/scratch": "x"}
TOUCHED = {"fresh/fresh": "touched"}


def write_all(directory: pathlib.Path, files: Mapping[str, str]) -> None:
    """Write files under a directory.

    Args:
        directory: the directory.
        files: each file's path under it, and its content.
    """
    for name, text in files.items():
        fakes.write(directory / name, text)


def age(path: pathlib.Path) -> None:
    """Make everything under a directory ten hours old.

    Args:
        path: the directory.
    """
    for directory, _, files in os.walk(path):
        for name in [*files, "."]:
            os.utime(pathlib.Path(directory) / name, (OLD, OLD))


def add_worktree(clone: pathlib.Path, name: str) -> pathlib.Path:
    """Add a worktree on a new branch, with one commit of its own.

    Args:
        clone: the main clone.
        name: the worktree's and the branch's name.

    Returns:
        The worktree.
    """
    path = fakes.add_worktree(clone, name)
    fakes.commit_file(path, name)
    return path


def add_detached(clone: pathlib.Path, path: pathlib.Path) -> None:
    """Add a worktree at the clone's tip, on no branch.

    Args:
        clone: the main clone.
        path: where.
    """
    fakes.run_git(clone, "worktree", "add", "-q", "--detach", str(path))


def scene() -> tuple[pathlib.Path, pathlib.Path]:
    """A clone with a worktree for every rule, all old but ``fresh``.

    Returns:
        The workspace and the clone.
    """
    workspace = fakes.directory()
    clone = fakes.make_repository(workspace)
    for name in PUSHED:
        fakes.push(add_worktree(clone, name))
    add_worktree(clone, "unpushed")
    for name in DETACHED:
        add_detached(clone, workspace / name)
    outside = fakes.directory() / "outside"
    add_detached(clone, outside)
    shutil.rmtree(workspace / "gone")
    write_all(workspace, UNCOMMITTED)
    for path in [workspace, outside]:
        age(path)
    write_all(workspace, TOUCHED)
    return workspace, clone


def reasons(
    workspace: pathlib.Path, clone: pathlib.Path
) -> Mapping[str, local.Reason | None]:
    """Decide about every worktree of the clone.

    Args:
        workspace: the workspace.
        clone: the main clone.

    Returns:
        Each worktree's directory name and why it is stale, or None.
    """
    sweeper = local.Sweeper(
        run=fakes.FakeProcesses(bodies={}),
        settings=fakes.settings(workspace),
        outcomes=OUTCOMES,
        cutoff=CUTOFF,
    )
    listed = fakes.run_git(clone, "worktree", "list", "--porcelain")
    return {
        worktree.path.name: local.stale_reason(sweeper, worktree)
        for worktree in local.parse_worktrees(listed)
    }


class TestStragglers(unittest.TestCase):
    """Work that exists only on this machine."""

    def test_stragglers(self) -> None:
        """A clean checkout is not one; changes and unpushed commits are."""
        workspace = fakes.directory()
        clone = fakes.make_repository(workspace)
        fakes.write(workspace / "not-a-checkout" / "file", "")
        runner = fakes.FakeProcesses(bodies={})
        before = (local.checkouts(workspace), local.read_straggler(runner, clone))
        fakes.run_git(clone, "checkout", "-q", "-b", "work")
        fakes.commit_file(clone, "local-work")
        fakes.write(clone / "unsaved", "x")
        found = local.read_straggler(runner, clone)
        assert_that(before, equal_to(([clone], None)))
        assert_that(
            found and (found.uncommitted, found.unpushed, found.on_origin),
            equal_to((1, 1, False)),
        )
        assert_that(found and found.last.endswith("local-work"), equal_to(True))

    def test_fetch_once_per_repository(self) -> None:
        """Worktrees of one repository are fetched once; a failure is named."""
        workspace = fakes.directory()
        clone = fakes.make_repository(workspace)
        worktree = add_worktree(clone, "worktree")
        broken = fakes.make_unfetchable(workspace, "broken")
        empty = fakes.make_unfetchable(workspace, "empty")
        runner = fakes.FakeProcesses(bodies={})
        failed = local.fetch_each_repository(runner, [clone, worktree, broken])
        fetches = [call for call in runner.calls if "fetch" in call]
        found = (failed, len(fetches), local.unpushed(runner, empty))
        assert_that(found, equal_to(([str(broken)], 2, 0)))


class TestWorktrees(unittest.TestCase):
    """Which worktrees are stale."""

    def test_reasons(self) -> None:
        """Each rule keeps or marks its worktree."""
        found = reasons(*scene())
        stale = {name: reason for name, reason in found.items() if reason is not None}
        assert_that((stale, len(found)), equal_to((STALE, 11)))

    def test_touched_only_near_the_top(self) -> None:
        """Changes deeper than three levels, or in .git, do not count."""
        top = fakes.directory()
        deep = top / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (top / ".git").mkdir()
        age(top)
        for path in [deep / "new", top / ".git" / "index"]:
            fakes.write(path, "new")
        before = local.touched_since(top, CUTOFF)
        fakes.write(top / "a" / "new", "new")
        assert_that((before, local.touched_since(top, CUTOFF)), equal_to((False, True)))

    def test_listing(self) -> None:
        """An empty listing has no worktrees; a branch keeps its newest PR."""
        api = fakes.github({ALL_PULLS: TWO_PULLS})
        found = local.read_outcomes(api, config.make_repo("o", "r"))
        assert_that(
            (local.parse_worktrees(""), found["b"].still_open), equal_to(([], True))
        )

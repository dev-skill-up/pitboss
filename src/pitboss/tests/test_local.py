"""Tests for stragglers and stale worktrees, on real git repositories."""

import contextlib
import dataclasses
import io
import os
import pathlib
import shutil
import time
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config, local, shapes
from . import fakes, orphans, repositories, scratch

OLD = time.time() - 10 * 3600
CUTOFF = OLD + 3600
PUSHED = ("merged", "closed", "open", "no-pull")
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


def age(path: pathlib.Path) -> None:
    """Make everything under a directory ten hours old.

    Args:
        path: the directory.
    """
    for directory, _, files in os.walk(path):
        for name in [*files, "."]:
            there = pathlib.Path(directory) / name
            os.utime(there, (OLD, OLD), follow_symlinks=False)


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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Stale:
    """A clone with a worktree for every rule, which no test changes.

    Attributes:
        workspace: the workspace.
        clone: the main clone.
        outside: the directory with the worktree outside the workspace.
        origins: the origins its repositories came from.
    """

    workspace: pathlib.Path
    clone: pathlib.Path
    outside: pathlib.Path
    origins: Sequence[pathlib.Path]


@scratch.built_once
def scene_template() -> Stale:
    """A clone with a worktree for every rule, all old but ``fresh``.

    Built by the first test that asks, with real git.

    Returns:
        The scene, which no test changes.
    """
    start = len(repositories.MADE)
    workspace = fakes.directory()
    clone = repositories.make_repository(workspace)
    for name in PUSHED:
        fakes.push(add_worktree(clone, name))
    add_worktree(clone, "unpushed")
    for name in DETACHED:
        add_detached(clone, workspace / name)
    outside = fakes.directory() / "outside"
    add_detached(clone, outside)
    shutil.rmtree(workspace / "gone")
    for path in [workspace, outside]:
        age(path)
    origins = tuple(repositories.MADE[start:])
    return Stale(workspace=workspace, clone=clone, outside=outside, origins=origins)


def scene() -> tuple[pathlib.Path, pathlib.Path]:
    """A copy of a clone with a worktree for every rule, all old but ``fresh``.

    Returns:
        The workspace and the clone.
    """
    made = scene_template()
    moved = repositories.copied([made.workspace, made.outside.parent], made.origins)
    workspace = repositories.shifted(made.workspace, moved)
    return workspace, repositories.shifted(made.clone, moved)


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
    )
    listed = fakes.run_git(clone, "worktree", "list", "--porcelain")
    return {
        worktree.path.name: local.finished_reason(sweeper, worktree)
        for worktree in local.parse_worktrees(listed)
    }


class TestStragglers(unittest.TestCase):
    """Work that exists only on this machine."""

    def test_stragglers(self) -> None:
        """A clean checkout is not one; changes and unpushed commits are."""
        workspace = fakes.directory()
        clone = repositories.make_repository(workspace)
        fakes.write(workspace / "not-a-checkout/file", "")
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

    def test_a_checkout_git_cannot_read_is_named_not_raised(self) -> None:
        """A broken .git is one more checkout whose fetch failed."""
        workspace = fakes.directory()
        broken = workspace / "broken"
        (broken / ".git").mkdir(parents=True)
        runner = fakes.FakeProcesses(bodies={})
        failed = local.fetch_each_repository(runner, [broken])
        assert_that(failed, equal_to([str(broken)]))

    def test_an_orphaned_checkout_is_told_from_a_readable_one(self) -> None:
        """A .git file pointing at a missing gitdir is orphaned (#98)."""
        workspace = fakes.directory()
        clone = repositories.make_repository(workspace)
        orphan = orphans.make_orphaned(workspace, "orphan")
        runner = fakes.FakeProcesses(bodies={})
        found = (local.orphaned(runner, clone), local.orphaned(runner, orphan))
        assert_that(found, equal_to((False, True)))

    def test_fetch_once_per_repository(self) -> None:
        """Worktrees of one repository are fetched once; a failure is named."""
        workspace = fakes.directory()
        clone = repositories.make_repository(workspace)
        worktree = add_worktree(clone, "worktree")
        broken = fakes.make_unfetchable(workspace, "broken")
        empty = fakes.make_unfetchable(workspace, "empty")
        runner = fakes.FakeProcesses(bodies={})
        failed = local.fetch_each_repository(runner, [clone, worktree, broken])
        fetches = [call for call in runner.calls if "fetch" in call]
        found = (failed, len(fetches), local.unpushed(runner, empty))
        assert_that(found, equal_to(([str(broken)], 2, 0)))

    def test_a_fetch_over_three_seconds_is_named_on_stderr(self) -> None:
        """Only a fetch over 3 seconds gets its line (keyword: slow-fetch)."""
        workspace = fakes.directory()
        clone = repositories.make_repository(workspace)
        runner = fakes.FakeProcesses(bodies={})
        said = {}
        for took in (1, 3, 4, 9):
            ticks = iter((0.0, float(took)))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                local.fetch_each_repository(runner, [clone], lambda: next(ticks))
            said[took] = err.getvalue()
        assert_that(
            said,
            equal_to(
                {
                    1: "",
                    3: "",
                    4: f"[pitboss] fetch in {clone} took 4s\n",
                    9: f"[pitboss] fetch in {clone} took 9s\n",
                }
            ),
        )


class TestWorktrees(unittest.TestCase):
    """Which worktrees are finished."""

    def test_reasons(self) -> None:
        """Each rule keeps or marks its worktree."""
        found = reasons(*scene())
        stale = {name: reason for name, reason in found.items() if reason is not None}
        assert_that((stale, len(found)), equal_to((STALE, 9)))

    def test_listing(self) -> None:
        """An empty listing has no worktrees; a branch keeps its newest PR."""
        api = fakes.github({ALL_PULLS: TWO_PULLS})
        found = local.read_outcomes(api, config.make_repo("o", "r"))
        assert_that(
            (local.parse_worktrees(""), found["b"].still_open), equal_to(([], True))
        )

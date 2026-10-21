"""Tests for stragglers and stale worktrees, on real git repositories."""

import os
import pathlib
import shutil
import tempfile
import time
import unittest

from hamcrest import assert_that, contains_exactly, ends_with, equal_to, is_, none

from .. import config, local, shapes
from . import fakes

OLD = time.time() - 10 * 3600


def _age(path: pathlib.Path) -> None:
    for directory, _, files in os.walk(path):
        for name in [*files, "."]:
            os.utime(pathlib.Path(directory) / name, (OLD, OLD))


class TestStragglers(unittest.TestCase):
    """Work that exists only on this machine."""

    def setUp(self) -> None:
        """Make a workspace with a clone."""
        self.workspace = pathlib.Path(tempfile.mkdtemp())
        self.origin, self.clone = fakes.make_repository(self.workspace)
        (self.workspace / "not-a-checkout").mkdir()
        self.run = fakes.FakeProcesses(bodies={})

    def test_clean_checkout(self) -> None:
        """A checkout with everything pushed is not a straggler."""
        assert_that(local.checkouts(self.workspace), contains_exactly(self.clone))
        assert_that(local.read_straggler(self.run, self.clone), is_(none()))

    def test_dirty_and_unpushed(self) -> None:
        """Uncommitted files and unpushed commits make a straggler."""
        fakes.run_git(self.clone, "checkout", "-q", "-b", "work")
        (self.clone / "new").write_text("x")
        fakes.run_git(self.clone, "add", "new")
        fakes.run_git(self.clone, "commit", "-q", "-m", "local work")
        (self.clone / "other").write_text("y")
        found = local.read_straggler(self.run, self.clone)
        assert_that(found and found.uncommitted, equal_to(1))
        assert_that(found and found.unpushed, equal_to(1))
        assert_that(found and found.on_origin, is_(False))
        assert_that(found and found.last, ends_with("local work"))

    def test_fetch_once_per_repository(self) -> None:
        """Worktrees of one repository are fetched once; a failure is named."""
        worktree = self.workspace / "worktree"
        fakes.run_git(self.clone, "worktree", "add", "-q", str(worktree), "-b", "w")
        broken = self.workspace / "broken"
        fakes.run_git(self.workspace, "init", "-q", str(broken))
        fakes.run_git(broken, "remote", "add", "origin", "/nowhere")
        failed = local.fetch_each_repository(
            self.run, [self.clone, worktree, broken]
        )
        assert_that(failed, contains_exactly(str(broken)))
        fetches = [call for call in self.run.calls if "fetch" in call]
        assert_that(len(fetches), equal_to(2))

    def test_empty_repository(self) -> None:
        """A repository with no commits has nothing unpushed."""
        empty = self.workspace / "empty"
        fakes.run_git(self.workspace, "init", "-q", str(empty))
        assert_that(local.unpushed(self.run, empty), equal_to(0))


class TestWorktrees(unittest.TestCase):
    """Which worktrees are stale."""

    def setUp(self) -> None:
        """Make a clone with worktrees."""
        self.workspace = pathlib.Path(tempfile.mkdtemp())
        self.origin, self.clone = fakes.make_repository(self.workspace)
        self.settings = fakes.settings(self.workspace)
        self.run = fakes.FakeProcesses(bodies={})

    def _worktree(self, name: str, *, push: bool = False) -> pathlib.Path:
        path = self.workspace / name
        fakes.run_git(self.clone, "worktree", "add", "-q", str(path), "-b", name)
        (path / name).write_text(name)
        fakes.run_git(path, "add", name)
        fakes.run_git(path, "commit", "-q", "-m", name)
        if push:
            fakes.run_git(path, "push", "-q", "origin", name)
        return path

    def _reasons(self, outcomes: dict[str, shapes.Outcome]) -> dict[str, object]:
        sweeper = local.Sweeper(
            run=self.run, settings=self.settings, outcomes=outcomes, cutoff=OLD + 3600
        )
        listed = fakes.run_git(self.clone, "worktree", "list", "--porcelain")
        return {
            worktree.path.name: local.stale_reason(sweeper, worktree)
            for worktree in local.parse_worktrees(listed)
        }

    def test_reasons(self) -> None:
        """Each rule keeps or marks its worktree."""
        for name in ["merged", "closed", "open", "unpushed", "dirty", "fresh"]:
            self._worktree(name, push=name != "unpushed")
        in_base = self.workspace / "in-base"
        fakes.run_git(self.clone, "worktree", "add", "-q", "--detach", str(in_base))
        no_pull = self._worktree("no-pull", push=True)
        (self.workspace / "dirty" / "scratch").write_text("x")
        _age(self.workspace)
        (self.workspace / "fresh" / "fresh").write_text("touched")
        outcome = shapes.Outcome
        found = self._reasons(
            {
                "merged": outcome(branch="merged", still_open=False, merged=True),
                "closed": outcome(branch="closed", still_open=False, merged=False),
                "open": outcome(branch="open", still_open=True, merged=False),
            }
        )
        assert_that(
            found,
            equal_to(
                {
                    "project": None,
                    "merged": local.Reason.MERGED,
                    "closed": local.Reason.CLOSED,
                    "open": None,
                    "unpushed": None,
                    "dirty": None,
                    "fresh": None,
                    "in-base": local.Reason.IN_BASE,
                    no_pull.name: None,
                }
            ),
        )

    def test_outside_workspace(self) -> None:
        """A worktree outside the workspace, or gone, is kept."""
        outside = pathlib.Path(tempfile.mkdtemp()) / "outside"
        fakes.run_git(self.clone, "worktree", "add", "-q", "--detach", str(outside))
        gone = self.workspace / "gone"
        fakes.run_git(self.clone, "worktree", "add", "-q", "--detach", str(gone))
        shutil.rmtree(gone)
        found = self._reasons({})
        assert_that(found["outside"], is_(none()))
        assert_that(found["gone"], is_(none()))

    def test_parse_nothing(self) -> None:
        """An empty listing has no worktrees."""
        assert_that(local.parse_worktrees(""), equal_to([]))

    def test_touched_only_near_the_top(self) -> None:
        """Changes deeper than three levels, or in .git, do not count."""
        top = pathlib.Path(tempfile.mkdtemp())
        deep = top / "a" / "b" / "c" / "d"
        deep.mkdir(parents=True)
        (top / ".git").mkdir()
        (top / ".git" / "index").write_text("new")
        _age(top)
        (deep / "new").write_text("new")
        (top / ".git" / "index").write_text("newer")
        assert_that(local.touched_since(top, OLD + 3600), is_(False))
        (top / "a" / "new").write_text("new")
        assert_that(local.touched_since(top, OLD + 3600), is_(True))

    def test_outcomes(self) -> None:
        """Each branch keeps its newest PR's outcome."""
        api = fakes.github(
            {
                fakes.page("repos/o/r/pulls?state=all"): [
                    {"head": {"ref": "b"}, "state": "open"},
                    {"head": {"ref": "b"}, "state": "closed", "merged_at": "x"},
                ]
            }
        )
        found = local.read_outcomes(api, config.Repo(owner="o", name="r"))
        assert_that(found["b"].still_open, is_(True))

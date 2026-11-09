"""The shared clones stay on their default branch, clean (keyword: clone-guard).

Tests for ``cloneguard``, ``hand-back-check``, ``nox`` and ``plan-check``
(pitboss#297).
"""

import dataclasses
import pathlib
import subprocess
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, not_

from .. import cloneguard
from . import fakes, repositories, world
from .plancheckrun import body_of
from .linting import write_text
from .test_deviations import WITH_NONE, WITHOUT_LINE, saved
from .test_nox import Done, FakeNox

REFUSAL = (
    "refused: this is the main clone; work in your own worktree:"
    " git worktree add -b <branch> <path> origin/main"
)


def tracked_file(clone: pathlib.Path) -> pathlib.Path:
    """The first file the clone tracks.

    Args:
        clone: the clone.

    Returns:
        Its path.
    """
    return clone / repositories.run_git(clone, "ls-files").split()[0]


def change(clone: pathlib.Path) -> None:
    """Leave an uncommitted change to a tracked file.

    Args:
        clone: the clone.
    """
    tracked_file(clone).write_text("changed by a worker\n", encoding="utf-8")


def check(here: world.World, text: str = WITH_NONE) -> world.Result:
    """Run ``hand-back-check`` with the world's configuration.

    Args:
        here: the world.
        text: the hand-back.

    Returns:
        What it did.
    """
    return world.invoke(
        here, "hand-back-check", saved(text), "--config", here.config
    )


class TestTheHandBack(unittest.TestCase):
    """``hand-back-check`` looks at every clone the configuration names."""

    def test_a_clone_on_main_with_no_change_passes(self) -> None:
        """The world's main clone is on main and clean."""
        found = check(world.make_world())
        assert_that((found.code, found.out), equal_to((0, "ok\n")))

    def test_an_untracked_file_is_not_a_change(self) -> None:
        """A clone keeps files of its own that git does not track."""
        here = world.make_world()
        (here.clone / "scratch.txt").write_text("x", encoding="utf-8")
        assert_that(check(here).code, equal_to(0))

    def test_a_clone_on_a_side_branch_is_refused_with_its_branch(self) -> None:
        """The refusal prints the clone and the branch it is on."""
        here = world.make_world()
        repositories.run_git(here.clone, "checkout", "-q", "-b", "publish-zip-95")
        found = check(here)
        assert_that(found.code, equal_to(1))
        assert_that(found.out, contains_string(f"clone {here.clone} is on branch"))
        assert_that(found.out, contains_string("publish-zip-95, not main"))
        assert_that(found.out, not_(contains_string("ok")))

    def test_a_detached_clone_is_refused(self) -> None:
        """A clone on no branch is on no default branch."""
        here = world.make_world()
        repositories.run_git(here.clone, "checkout", "-q", "--detach")
        found = check(here)
        assert_that(found.code, equal_to(1))
        assert_that(found.out, contains_string("(detached HEAD)"))

    def test_a_clone_with_a_change_is_refused(self) -> None:
        """An edit of a tracked file is named, with the branch."""
        here = world.make_world()
        change(here.clone)
        found = check(here)
        assert_that(found.code, equal_to(1))
        assert_that(
            found.out,
            contains_string(f"clone {here.clone} (branch main) has uncommitted"),
        )

    def test_a_library_clone_off_main_is_refused(self) -> None:
        """The clones of the libraries under the workspace are judged too."""
        here = world.make_world()
        library = here.workspace / "lib"
        repositories.run_git(here.workspace, "init", "-q", "-b", "side", str(library))
        found = check(here)
        assert_that(found.code, equal_to(1))
        assert_that(found.out, contains_string(f"clone {library} is on branch side"))

    def test_both_the_missing_line_and_the_clone_are_said(self) -> None:
        """The two refusals are independent."""
        here = world.make_world()
        change(here.clone)
        found = check(here, WITHOUT_LINE)
        assert_that(found.code, equal_to(1))
        assert_that(found.out, contains_string("NOT STARTED"))
        assert_that(found.out, contains_string("uncommitted"))

    def test_a_configuration_that_cannot_be_read_is_a_usage_error(self) -> None:
        """No clone can be judged by a configuration that is not there."""
        here = world.make_world()
        found = world.invoke(
            here,
            "hand-back-check",
            saved(WITH_NONE),
            "--config",
            str(here.workspace / "missing.toml"),
        )
        assert_that(found.code, equal_to(2))


def real_git(command: Sequence[str]) -> Done:
    """Answer a ``git -C`` command line for real, and any other as unsayable.

    Args:
        command: the command line.

    Returns:
        The finished process.
    """
    if command[1] != "-C":
        return Done(returncode=1, stdout="")
    done = subprocess.run(  # noqa: S603
        list(command), check=False, capture_output=True, text=True
    )
    return Done(returncode=done.returncode, stdout=done.stdout)


def nox_in(here: world.World, directory: pathlib.Path) -> world.Result:
    """Run ``pitboss nox`` in a directory with a nox that is not run.

    Args:
        here: the world.
        directory: where it runs.

    Returns:
        What it did.
    """
    fake = FakeNox(statuses={}, calls=[], git=real_git)
    moved = dataclasses.replace(here, processes=fake)  # type: ignore[arg-type]
    return world.invoke(
        moved, "nox", "--config", here.config, directory=directory
    )


class TestNox(unittest.TestCase):
    """``nox`` does not run in the main clone with a change."""

    def test_the_main_clone_with_a_change_is_refused(self) -> None:
        """The line is exact, the status 1, and no session ran."""
        here = world.make_world()
        change(here.clone)
        found = nox_in(here, here.clone)
        assert_that((found.code, found.out), equal_to((1, REFUSAL + "\n")))

    def test_a_worktree_with_a_change_runs(self) -> None:
        """A worktree is not the clone, whatever it holds."""
        here = world.make_world()
        change(here.worktree)
        found = nox_in(here, here.worktree)
        assert_that(found.code, equal_to(0))
        assert_that(found.out, not_(contains_string("refused")))

    def test_the_clean_main_clone_runs(self) -> None:
        """Only a clone with a change is refused."""
        here = world.make_world()
        found = nox_in(here, here.clone)
        assert_that(found.code, equal_to(0))

    def test_a_directory_outside_any_checkout_runs(self) -> None:
        """No checkout, no clone."""
        here = world.make_world()
        outside = fakes.directory() / "plain"
        outside.mkdir()
        assert_that(nox_in(here, outside).code, equal_to(0))

    def test_no_configuration_refuses_nothing(self) -> None:
        """Without a configuration no clone is known."""
        here = world.make_world()
        change(here.clone)
        fake = FakeNox(statuses={}, calls=[], git=real_git)
        moved = dataclasses.replace(here, processes=fake)  # type: ignore[arg-type]
        found = world.invoke(moved, "nox", directory=here.clone)
        assert_that(found.out, not_(contains_string("refused")))


class TestPlanCheck(unittest.TestCase):
    """``plan-check`` does not run in the main clone with a change."""

    def run_in(self, here: world.World, repo: pathlib.Path) -> world.Result:
        """Run ``plan-check`` on a body for a checkout.

        Args:
            here: the world.
            repo: the checkout.

        Returns:
            What it did.
        """
        body = write_text("body.txt", body_of("1. `true`\n"))
        return world.invoke(
            here,
            "plan-check",
            body,
            "--repo",
            str(repo),
            "--config",
            here.config,
            directory=repo,
        )

    def test_the_main_clone_with_a_change_is_refused(self) -> None:
        """The line is exact and the status 1."""
        here = world.make_world()
        change(here.clone)
        found = self.run_in(here, here.clone)
        assert_that((found.code, found.out), equal_to((1, REFUSAL + "\n")))

    def test_a_worktree_with_a_change_is_not_refused(self) -> None:
        """A worktree is not the clone."""
        here = world.make_world()
        change(here.worktree)
        found = self.run_in(here, here.worktree)
        assert_that(found.out, not_(contains_string(REFUSAL)))


class TestTheText(unittest.TestCase):
    """The words the guard says."""

    def test_the_refusal_names_the_command_to_run(self) -> None:
        """The exact text the ticket gives."""
        assert_that(cloneguard.REFUSED, equal_to(REFUSAL))

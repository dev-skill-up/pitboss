"""The shared clones stay on their default branch, clean (keyword: clone-guard).

Tests for ``cloneguard``, ``hand-back-check``, ``nox`` and ``plan-check``
(pitboss#297).
"""

import dataclasses
import itertools
import pathlib
import subprocess
import unittest
from typing import Callable, Mapping, Sequence

from hamcrest import (
    all_of,
    assert_that,
    contains_string,
    equal_to,
    has_properties,
    not_,
)

from .. import cloneguard
from . import fakes, repositories, world
from .linting import write_text
from .plancheckrun import body_of
from .test_deviations import WITH_NONE, WITHOUT_LINE, saved
from .test_nox import Done, FakeNox

REFUSAL = (
    "refused: this is the main clone; work in your own worktree:"
    " git worktree add -b <branch> <path> origin/main"
)
Setup = Callable[[world.World], None]


def change(here: world.World) -> None:
    """Leave an uncommitted change to a tracked file of the main clone.

    Args:
        here: the world.
    """
    names = repositories.run_git(here.clone, "ls-files").split()
    (here.clone / names[0]).write_text("changed by a worker\n", encoding="utf-8")


def side_branch(here: world.World) -> None:
    """Check the main clone out to a branch of a worker.

    Args:
        here: the world.
    """
    repositories.run_git(here.clone, "checkout", "-q", "-b", "publish-zip-95")


def detached(here: world.World) -> None:
    """Check the main clone out to no branch.

    Args:
        here: the world.
    """
    repositories.run_git(here.clone, "checkout", "-q", "--detach")


def library_on_side(here: world.World) -> None:
    """Make the clone of the library, on a branch that is not main.

    Args:
        here: the world.
    """
    library = here.workspace / "lib"
    repositories.run_git(here.workspace, "init", "-q", "-b", "side", str(library))


def untracked(here: world.World) -> None:
    """Add a file git does not track to the main clone.

    Args:
        here: the world.
    """
    (here.clone / "scratch.txt").write_text("x", encoding="utf-8")


def nothing(here: world.World) -> None:
    """Leave the world as it is.

    Args:
        here: the world.
    """


def check(here: world.World, text: str = WITH_NONE) -> world.Result:
    """Run ``hand-back-check`` with the world's configuration.

    Args:
        here: the world.
        text: the hand-back.

    Returns:
        What it did.
    """
    return world.invoke(here, "hand-back-check", saved(text), "--config", here.config)


REFUSED: Mapping[str, tuple[Setup, str]] = {
    "side branch": (side_branch, "publish-zip-95, not main"),
    "detached": (detached, "on branch (detached HEAD), not main"),
    "change": (change, "(branch main) has uncommitted changes"),
    "library": (library_on_side, "lib on branch side, not main"),
}
PASSED: Mapping[str, Setup] = {
    "clean": nothing,
    "untracked": untracked,
}


class TestTheHandBack(unittest.TestCase):
    """``hand-back-check`` looks at every clone the configuration names."""

    def test_a_clone_off_main_or_with_a_change_is_refused_by_name(self) -> None:
        """The refusal prints the clone and its branch, and the status is 1."""
        for name, (setup, wanted) in REFUSED.items():
            with self.subTest(name):
                here = world.make_world()
                setup(here)
                found = check(here)
                said = all_of(
                    contains_string("refused: clone "), contains_string(wanted)
                )
                assert_that(found, has_properties(code=1, out=said))

    def test_a_clone_on_main_with_no_change_passes(self) -> None:
        """A file git does not track is not a change."""
        for name, setup in PASSED.items():
            with self.subTest(name):
                here = world.make_world()
                setup(here)
                found = check(here)
                assert_that((found.code, found.out), equal_to((0, "ok\n")))

    def test_both_the_missing_line_and_the_clone_are_said(self) -> None:
        """The two refusals are independent."""
        here = world.make_world()
        change(here)
        found = check(here, WITHOUT_LINE)
        said = all_of(contains_string("NOT STARTED"), contains_string("uncommitted"))
        assert_that(found, has_properties(code=1, out=said))

    def test_a_configuration_that_cannot_be_read_is_a_usage_error(self) -> None:
        """Given and missing, or given and not TOML: status 2, no verdict."""
        here = world.make_world()
        broken = write_text("broken.toml", "[project\n")
        names = (str(here.workspace / "missing.toml"), broken)
        found = [
            world.invoke(here, "hand-back-check", saved(WITH_NONE), "--config", each)
            for each in names
        ]
        assert_that([each.code for each in found], equal_to([2, 2]))
        assert_that([each.out for each in found], equal_to(["", ""]))


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


def nox_in(here: world.World, directory: pathlib.Path, *more: str) -> world.Result:
    """Run ``pitboss nox`` in a directory with a nox that is not run.

    Args:
        here: the world.
        directory: where it runs.
        *more: the words after the command.

    Returns:
        What it did.
    """
    fake = FakeNox(statuses={}, calls=[], git=real_git)
    moved = dataclasses.replace(here, processes=fake)  # type: ignore[arg-type]
    return world.invoke(moved, "nox", *more, directory=directory)


def plan_check_in(
    here: world.World, directory: pathlib.Path, *more: str
) -> world.Result:
    """Run ``pitboss plan-check`` on a body for the checkout in a directory.

    Args:
        here: the world.
        directory: the checkout, where it runs.
        *more: the words after the command.

    Returns:
        What it did.
    """
    body = write_text("body.txt", body_of("1. `true`\n"))
    return world.invoke(
        here, "plan-check", body, "--repo", str(directory), *more, directory=directory
    )


class TestTheCheckout(unittest.TestCase):
    """``nox`` and ``plan-check`` do not run in the main clone with a change."""

    def test_the_main_clone_with_a_change_is_refused(self) -> None:
        """The line is exact, the status 1, and nothing else is printed."""
        for run in (nox_in, plan_check_in):
            with self.subTest(run.__name__):
                here = world.make_world()
                change(here)
                found = run(here, here.clone, "--config", here.config)
                assert_that((found.code, found.out), equal_to((1, REFUSAL + "\n")))

    def test_a_worktree_a_clean_clone_or_no_checkout_is_not_refused(self) -> None:
        """Only the clone itself, with a change, is the main clone."""
        dirty, clean = world.make_world(), world.make_world()
        change(dirty)
        names = repositories.run_git(dirty.worktree, "ls-files").split()
        (dirty.worktree / names[0]).write_text("edited\n", encoding="utf-8")
        outside = fakes.directory() / "plain"
        outside.mkdir()
        places = [(dirty, dirty.worktree), (clean, clean.clone), (clean, outside)]
        for run, (here, directory) in itertools.product(
            (nox_in, plan_check_in), places
        ):
            with self.subTest(run.__name__, directory=directory):
                found = run(here, directory, "--config", here.config)
                assert_that(found.out, not_(contains_string(REFUSAL)))

    def test_with_no_configuration_no_clone_is_known(self) -> None:
        """``nox`` finds none from this directory, and refuses nothing."""
        here = world.make_world()
        change(here)
        found = nox_in(here, here.clone)
        assert_that(found.out, not_(contains_string(REFUSAL)))

    def test_the_text_is_the_tickets(self) -> None:
        """The words of the refusal are pinned."""
        assert_that(cloneguard.REFUSED, equal_to(REFUSAL))

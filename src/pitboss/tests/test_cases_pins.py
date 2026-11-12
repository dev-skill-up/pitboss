"""I31 of pitboss#444: pins-review leaves the clone on its branch; hand-back-check
reads the repository from the worktree's origin, not from the configuration.
"""

import unittest

from hamcrest import assert_that, equal_to

from .. import pinsonly
from . import fakes
from .handbackrun import hand_back, processes
from .handbackworld import BASE, git, ready
from .test_pins_verify import checkout_for, pull_of, scripted, settings_for
from . import world


class TestPinsReviewBranch(unittest.TestCase):
    """The clone is returned to the branch it was on."""

    def test_i31_pins_review_returns_the_clone_to_its_branch(self) -> None:
        """A command that detaches the checkout leaves it on main again."""
        settings = settings_for("check {base} {head}")
        where = checkout_for(settings, settings.project.repo)
        before = fakes.run_git(where, "branch", "--show-current").strip()

        run = scripted(["OK\n"], [])
        head = fakes.run_git(where, "rev-parse", "HEAD").strip()

        def moving(cmdargs: object, /) -> object:
            done = run(cmdargs)  # type: ignore[arg-type]
            if cmdargs[0] == "env":  # type: ignore[index]
                fakes.run_git(where, "checkout", "--quiet", "--detach", head)
            return done

        pinsonly.verify(moving, settings, settings.project.repo, pull_of())  # type: ignore[arg-type]
        after = fakes.run_git(where, "branch", "--show-current").strip()
        assert_that((before, after), equal_to(("main", "main")))


class TestHandBackOrigin(unittest.TestCase):
    """The PR is looked up in the repository the worktree's origin names."""

    def test_i31_a_pr_of_a_second_repository_is_judged_with_the_first_ones_config(
        self,
    ) -> None:
        """The origin is other/lib; the config names owner/project."""
        here = ready(world.make_world())
        moved = {
            key.replace(BASE, "repos/other/lib").replace(
                "head=owner:", "head=other:"
            ): v
            for key, v in here.bodies.items()
        }
        here.bodies.update(moved)
        git(
            here.clone,
            "remote",
            "set-url",
            "origin",
            "https://github.com/other/lib.git",
        )
        done = hand_back(here, processes(fakes.directory(), {}))
        assert_that((done.code, done.out), equal_to((0, "ok\n")))

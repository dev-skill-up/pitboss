"""I31 of pitboss#444: hand-back-check reads the repository from origin."""

import unittest

from hamcrest import assert_that, equal_to

from .handbackrun import hand_back, no_jobs
from .handbackworld import BASE, git, ready
from . import world


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
        assert_that(hand_back(here, no_jobs()).out, equal_to("ok\n"))

    def test_an_origin_with_no_github_repository_is_refused(
        self,
    ) -> None:
        """pitboss#526: the configuration's repository is never the PR's."""
        here = ready(world.make_world())
        git(here.clone, "remote", "set-url", "origin", "http://127.0.0.1:9/git/x")
        out = hand_back(here, no_jobs()).out
        assert_that("names no GitHub repository" in out, equal_to(True))
        assert_that(out == "ok\n", equal_to(False))

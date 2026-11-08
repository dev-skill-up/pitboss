"""The test double of the processes runs git for real."""

import unittest

from hamcrest import assert_that, equal_to

from . import fakes


class TestFakeProcesses(unittest.TestCase):
    """What the double answers and what it runs."""

    def test_git_cannot_be_given_an_answer(self) -> None:
        """An answer for git is refused when git is run: git is run for real."""
        run = fakes.FakeProcesses(bodies={}, answers=dict(git=0))
        with self.assertRaisesRegex(ValueError, "git is run for real"):
            run(["git", "--version"])

    def test_git_runs_in_the_directory_it_is_given(self) -> None:
        """A command that is not answered runs for real, in the directory."""
        top = fakes.directory()
        fakes.run_git(top, "init", "-q")
        run = fakes.FakeProcesses(bodies={}, cwd=top)
        inside = run(["git", "rev-parse", "--is-inside-work-tree"]).stdout
        assert_that(inside, equal_to("true\n"))

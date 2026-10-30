"""The command line parser: options among a subcommand's positionals."""

import unittest
from collections.abc import Sequence

from hamcrest import assert_that, equal_to

from . import world


def parsed(*argv: str) -> tuple[str, bool, bool, Sequence[str]]:
    """What the parser makes of a ``pitboss push`` command line.

    Args:
        *argv: the words after ``pitboss push``.

    Returns:
        The config, ``--no-dry-run``, ``--draft`` and git's arguments.
    """
    found = world.parser().parse_args(["push", *argv])
    return (found.config, found.no_dry_run, found.draft, found.git_arguments)


class TestPushArguments(unittest.TestCase):
    """``pitboss push CONFIG`` takes git's arguments with options anywhere."""

    def test_options_before_git_arguments(self) -> None:
        """Options between the config and git's arguments (3.12.3 refused it)."""
        found = parsed("cfg", "--now", "x", "--no-dry-run", "origin", "branch-1")
        assert_that(found, equal_to(("cfg", True, False, ["origin", "branch-1"])))

    def test_options_after_git_arguments(self) -> None:
        """Options after git's arguments."""
        found = parsed("cfg", "origin", "branch-1", "--no-dry-run", "--draft")
        assert_that(found, equal_to(("cfg", True, True, ["origin", "branch-1"])))

    def test_double_dash_after_options(self) -> None:
        """``--`` ends the options, so git's own options go through."""
        found = parsed("cfg", "--draft", "--", "-f", "origin")
        assert_that(found, equal_to(("cfg", False, True, ["-f", "origin"])))

    def test_double_dash_alone(self) -> None:
        """``--`` straight after the config."""
        found = parsed("cfg", "--", "origin", "--now", "x")
        assert_that(found, equal_to(("cfg", False, False, ["origin", "--now", "x"])))

    def test_no_git_arguments(self) -> None:
        """No git arguments is an empty list."""
        assert_that(parsed("cfg"), equal_to(("cfg", False, False, [])))

"""A command's usage text is its docstring (keyword: command-help, pitboss#301)."""

import argparse
import contextlib
import io
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import cli_parser, commanddoc, machine


def shown(*argv: str) -> str:
    """What ``pitboss`` prints for a help request.

    Args:
        *argv: the words after ``pitboss``.

    Returns:
        The standard output.
    """
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
        cli_parser.make_parser(machine.read_usage).parse_args(list(argv))
    return out.getvalue()


def documented(command: str) -> str:
    """A command with a docstring that has an ``Args:`` section.

    Args:
        command: what it is given.

    Returns:
        What it is given.
    """
    return command


def unargued(args: argparse.Namespace) -> None:
    """Do nothing.

    Args:
        args: the parsed arguments.
    """
    return None


class TestCommandUsage(unittest.TestCase):
    """The usage names every command and says what each does."""

    def test_the_top_usage_lists_each_command_with_its_first_line(self) -> None:
        """``pitboss --help`` has a line for ``nox`` and for ``review-form``."""
        found = shown("--help")
        assert_that(
            found,
            contains_string(
                "  nox: Run the sessions of ``noxcheck.Session``, in their order."
            ),
        )
        assert_that(
            found,
            contains_string(
                "  review-form: Print the form a review comment in a repository"
                " must take."
            ),
        )

    def test_a_command_usage_has_its_whole_docstring_but_its_args(self) -> None:
        """``pitboss nox --help`` has the rest of the docstring, not ``Args:``."""
        found = shown("nox", "--help")
        assert_that(found, contains_string("Before it starts a session it reads"))
        assert_that("the parsed arguments" in found, equal_to(False))
        assert_that(found, contains_string("CI's Run Nox step"))

    def test_the_text_stops_at_args(self) -> None:
        """The text of a docstring with ``Args:`` is what comes before them."""
        assert_that(documented("given"), equal_to("given"))
        assert_that(
            commanddoc.text(documented),
            equal_to("A command with a docstring that has an ``Args:`` section."),
        )

    def test_the_described_text_follows_the_docstring(
        self,
    ) -> None:
        """A command described with a text has it after its docstring."""
        made = commanddoc.described("More.")(unargued)
        assert_that(made(argparse.Namespace()), equal_to(None))
        assert_that(commanddoc.text(made), equal_to("Do nothing.\n\nMore."))

    def test_a_function_without_a_docstring_has_no_text(self) -> None:
        """A callable with no docstring gives the empty text."""
        assert_that(commanddoc.text(lambda: None), equal_to(""))

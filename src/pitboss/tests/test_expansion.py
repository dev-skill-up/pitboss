"""Tests for the expansion of a template (keyword: expand, pitboss#117)."""

import dataclasses
import unittest
from typing import Mapping, MutableSequence

from hamcrest import assert_that, equal_to, has_length

from .. import expansion
from .linting import OK

RAW = "  a  \n\n\ttab\n"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RecordingShell:
    """A shell that answers each command from a table and records the order.

    Attributes:
        answers: each command line and what it did.
        ran: the commands run, in order.
    """

    answers: Mapping[str, expansion.Outcome]
    ran: MutableSequence[str] = dataclasses.field(default_factory=list)

    def __call__(self, command: str) -> expansion.Outcome:
        """Run a command.

        Args:
            command: the command line.

        Returns:
            What the table says it did.
        """
        self.ran.append(command)
        return self.answers[command]


def contents(command: str, status: int, output: str) -> str:
    """The lines inside the fences of a command's block.

    Args:
        command: the command line.
        status: its exit status.
        output: what it printed.

    Returns:
        The lines between the fences.
    """
    rows = expansion.block(command, expansion.Outcome(status=status, output=output))
    return "".join(rows.splitlines(keepends=True)[1:-1])


class TestBlock(unittest.TestCase):
    """The block of one command."""

    def test_the_lines_inside(self) -> None:
        """The command as written, the output exactly, a status only if nonzero."""
        cases = {
            "as written": (("x  ", 0, RAW), "$ x  \n" + RAW),
            "failed": (("x", 3, "bad\n"), "$ x\nbad\nexit status: 3\n"),
            "silent": (("true", 0, ""), "$ true\n"),
            "no newline": (
                ("printf x", 1, "no newline"),
                "$ printf x\nno newline\n\\ No newline at end of output\n"
                "exit status: 1\n",
            ),
        }
        for name, (given, shown) in cases.items():
            with self.subTest(name):
                assert_that(contents(*given), equal_to(shown))

    def test_fences(self) -> None:
        """The opening line has the mark and digest; output ticks lengthen the fence."""
        for output, fence in (("OK\n", "```"), ("```\nx\n```\n", "````")):
            with self.subTest(fence):
                rows = expansion.block("x", expansion.Outcome(status=0, output=output))
                mark = expansion.info(contents("x", 0, output))
                ends = [rows.splitlines()[0], rows.splitlines()[-1]]
                assert_that(ends, equal_to([f"{fence}{mark}", fence]))

    def test_digest_follows_the_contents(self) -> None:
        """A different command or output gives a different digest."""
        other = expansion.Outcome(status=0, output="OK!\n")
        digests = {
            expansion.digest("a"),
            expansion.digest("b"),
            expansion.info(contents("x", 0, "OK\n")),
            expansion.info(contents("x", 0, other.output)),
        }
        assert_that(digests, has_length(4))


class TestExpand(unittest.TestCase):
    """The expansion of a template."""

    def test_text_is_kept_and_commands_run_in_order(self) -> None:
        """Prose passes through unchanged; each directive becomes its block."""
        shell = RecordingShell(answers={"one": OK, "two": OK})
        template = "Fixes #1\n\n## Evidence\n$ one\nbetween\n$ two\nend\n"
        body = expansion.expand(template, shell)
        expected = (
            "Fixes #1\n\n## Evidence\n"
            + expansion.block("one", OK)
            + "between\n"
            + expansion.block("two", OK)
            + "end\n"
        )
        assert_that([body, shell.ran], equal_to([expected, ["one", "two"]]))

    def test_lines_that_are_not_directives(self) -> None:
        """Only a line that starts with the prompt runs; the line end is not kept."""
        shell = RecordingShell(answers={"one": OK})
        cases = {
            "\\$ not run\na $ b\n $ c\n": "$ not run\na $ b\n $ c\n",
            "$ one\r\n": expansion.block("one", OK),
            "$ one": expansion.block("one", OK),
        }
        for template, body in cases.items():
            with self.subTest(template):
                assert_that(expansion.expand(template, shell), equal_to(body))

    def test_empty_command_runs_nothing(self) -> None:
        """A directive with no command is refused before anything runs."""
        shell = RecordingShell(answers={"one": OK})
        with self.assertRaisesRegex(expansion.TemplateError, "line 2"):
            expansion.expand("$ one\n$  \n", shell)
        assert_that(shell.ran, has_length(0))

    def test_commands_lists_the_directives(self) -> None:
        """The commands of a template, as written."""
        listed = expansion.commands("x\n$ a b\n\\$ c\n$ d\n")
        assert_that(listed, equal_to(["a b", "d"]))

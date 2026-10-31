"""Tests for ``pitboss expand`` and its marks in ``lint pr-body`` (pitboss#117)."""

import dataclasses
import subprocess
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import expansion
from . import fakes, world
from .linting import FOOTER, HEAD, lines, lint, write_text

MISSING = "/nonexistent/template.md"
FAILING = "echo out; echo err >&2; exit 3"
COUNTED = "printf 'a\\nb\\n' | wc -l"
BINARY = "printf 'a\\r\\n\\377'"


def real_world() -> world.World:
    """A world whose commands really run, as ``pitboss expand`` does.

    Returns:
        The world.
    """
    # the test double of the processes only answers gh; the real runner is the point
    return dataclasses.replace(
        world.make_world(),
        processes=subprocess.run,  # type: ignore[arg-type]
    )


def expanded(template: str, *options: str) -> world.Result:
    """Run ``pitboss expand`` on a template.

    Args:
        template: the template's text.
        *options: options after the file.

    Returns:
        What it did.
    """
    return world.invoke(real_world(), "expand", write_text("t.md", template), *options)


def block_of(command: str, output: str, status: int = 0) -> str:
    """The block expand prints, built by the module under test's own rule.

    Args:
        command: the command line.
        output: what it printed.
        status: its exit status.

    Returns:
        The block.
    """
    return expansion.block(command, expansion.Outcome(status=status, output=output))


class TestExpandCommand(unittest.TestCase):
    """The command that fills a template."""

    def test_runs_in_the_given_checkout(self) -> None:
        """Commands run in --cwd and their output is printed as it came."""
        checkout = fakes.directory()
        fakes.write(checkout / "marker.txt", "  line one  \n\nlast\n")
        done = expanded("Text\n$ cat < marker.txt\nMore\n", "--cwd", str(checkout))
        shown = block_of("cat < marker.txt", "  line one  \n\nlast\n")
        assert_that([done.out, done.code], equal_to(["Text\n" + shown + "More\n", 0]))

    def test_what_the_commands_print(self) -> None:
        """Both streams, a status, a filter, raw bytes; the default directory."""
        done = expanded(f"$ {FAILING}\n$ {COUNTED}\n$ {BINARY}\n$ echo hi\n")
        expected = (
            block_of(FAILING, "out\nerr\n", 3)
            + block_of(COUNTED, "2\n")
            + block_of(BINARY, "a\r\n\\xff")
            + block_of("echo hi", "hi\n")
        )
        assert_that([done.out, done.code], equal_to([expected, 0]))

    def test_usage_errors(self) -> None:
        """Each bad template or directory exits 2 with nothing printed."""
        not_text = fakes.directory() / "t.md"
        not_text.write_bytes(b"\xff\n")
        ran = {
            "template": world.invoke(real_world(), "expand", MISSING),
            "directive": expanded("$ \n"),
            "cwd": expanded("$ true\n", "--cwd", MISSING),
            "encoding": world.invoke(real_world(), "expand", str(not_text)),
        }
        said = {
            "template": MISSING,
            "directive": "line 1",
            "cwd": "not a directory",
            "encoding": "t.md",
        }
        for name, done in ran.items():
            with self.subTest(name):
                assert_that([done.code, done.out], equal_to([2, ""]))
                assert_that(done.err, contains_string(said[name]))


def check(evidence: str) -> world.Result:
    """Lint a body whose Evidence section is the given text.

    Args:
        evidence: the text under the Evidence heading.

    Returns:
        What ``lint pr-body`` did.
    """
    body = f"Fixes #1\n\nHead: {HEAD}\n\n## Evidence\n\n{evidence}\n{FOOTER}\n"
    return lint("pr-body", write_text("body.md", body), "--head", HEAD)


class TestExpandThenLint(unittest.TestCase):
    """What expand prints passes the body lint; what is typed does not."""

    def test_expanded_body_passes(self) -> None:
        """The Evidence of a template run by expand is in form."""
        checked = check(expanded("$ echo hi\n").out)
        assert_that([lines(checked), checked.code], equal_to([["ok"], 0]))

    def test_typed_body_is_refused(self) -> None:
        """The same Evidence typed by hand is refused as hand-typed."""
        checked = check("```\n$ echo hi\nhi\n```\n")
        assert_that(checked.code, equal_to(1))
        assert_that(lines(checked)[0].endswith("(evidence)"), equal_to(True))
        assert_that(lines(checked)[1], contains_string("line 8"))
        assert_that(lines(checked)[1].endswith("(hand-typed)"), equal_to(True))

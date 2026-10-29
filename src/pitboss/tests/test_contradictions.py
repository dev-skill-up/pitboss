"""Tests for the contradiction checker and ``lint contradictions``."""

import pathlib
import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import contradictions, phrases
from .linting import lines, lint, write_text

DEFAULT_PAIRS = 6
PAIRS_FILE = "# mine\n\nba+r\tfoo\tbaaar\tfoo\tSay one thing.\n"
MORE_FILE = "zed\tqux\tzed\tqux\tOne.\n"
BAD_PAIR_FILES = [
    ("a\tb\tc\n", "mine:1: a pair has 5 fields separated by tabs, this"),
    ("# x\n(a)\tb\ta\tb\ti\n", "mine:2: (a): '(' is a group"),
    ("a\tb\tx\tb\ti\n", "mine:1: the example 'x' does not match its pattern"),
    ("a\tb\ta\tx\ti\n", "mine:1: the example 'x' does not match its pattern"),
]
SIDES = [
    ("what it cannot run is left to CI and said in the PR", "is not reported as a gap"),
    ("a p1 is not started while a p0 is open", "takes a p1 or lower only when none"),
    ("You own CI until it is green", "not necessarily you"),
    (
        "Nothing else in this file is the owner's word",
        "(owner, 2026-10-21) The orchestrator",
    ),
    ("The orchestrator removes a worktree", "Nobody deletes the checkout"),
    ("The orchestrator removes a finished worktree", "Nobody deletes the checkout"),
]


def shipped() -> Sequence[contradictions.Pair]:
    """The pairs pitboss ships.

    Returns:
        The pairs.
    """
    return contradictions.parse(contradictions.default_text(), "default")


def found_in(body: str, rules: Sequence[contradictions.Pair]) -> Sequence[str]:
    """The findings in one file.

    Args:
        body: the file's text.
        rules: the pairs.

    Returns:
        The findings.
    """
    return contradictions.findings([("t.md", body)], rules)


class TestPairsFiles(unittest.TestCase):
    """Reading a pairs file."""

    def test_parse_and_load(self) -> None:
        """Comments and blank lines are skipped; a file is read by its path."""
        path = pathlib.Path(write_text("mine.tsv", PAIRS_FILE))
        for found in (
            contradictions.parse(PAIRS_FILE, "mine"),
            contradictions.load(path),
        ):
            assert_that(
                [(one.first, one.second, one.instead) for one in found],
                equal_to([("ba+r", "foo", "Say one thing.")]),
            )

    def test_errors(self) -> None:
        """A line that is no pair, or a file that is missing, names its place."""
        for text, expected in BAD_PAIR_FILES:
            with self.assertRaises(phrases.PhraseError) as raised:
                contradictions.parse(text, "mine")
            assert_that(str(raised.exception), contains_string(expected))
        with self.assertRaises(phrases.PhraseError) as raised:
            contradictions.load(pathlib.Path("/no/such/pairs.tsv"))
        assert_that(str(raised.exception), contains_string("pairs.tsv: No such file"))


class TestShippedPairs(unittest.TestCase):
    """The pairs file pitboss ships."""

    def test_no_project_is_named(self) -> None:
        """The pairs name no project, file or ticket."""
        text = contradictions.default_text()
        assert_that(shipped(), has_length(DEFAULT_PAIRS))
        assert_that(
            re.findall(r"quire|bats|\.md|#\d{2,}", text, re.IGNORECASE), equal_to([])
        )

    def test_both_sides_are_found_and_one_side_is_not(self) -> None:
        """A text with both sides of a pair is found; one side is not."""
        verdicts = []
        for rule, (left, right) in zip(shipped(), SIDES, strict=True):
            both = found_in(f"{left}\n{right}\n", [rule])
            single = [*found_in(left, [rule]), *found_in(right, [rule])]
            verdicts.append((len(both), len(single)))
        assert_that(verdicts, equal_to([(2, 0)] * DEFAULT_PAIRS))


class TestSearch(unittest.TestCase):
    """Searching texts."""

    def test_the_line_of_each_side_is_printed(self) -> None:
        """A finding for each side names the other side's place."""
        rules = contradictions.parse(PAIRS_FILE, "mine")
        files = [("a.md", "x\nbaaar\n"), ("b.md", "FOO here\n")]
        assert_that(
            contradictions.findings(files, rules),
            equal_to(
                [
                    'a.md:2: contradiction: the line "baaar" is one side of a pair'
                    " with b.md:1: Say one thing.",
                    'b.md:1: contradiction: the line "FOO here" is one side of a'
                    " pair with a.md:2: Say one thing.",
                ]
            ),
        )

    def test_code_spans_and_long_lines(self) -> None:
        """A side in a code span is no side; a long line is shown cut."""
        rules = contradictions.parse(PAIRS_FILE, "mine")
        assert_that(found_in("baaar `foo` and `x`\n", rules), equal_to([]))
        cut = found_in("bar " + "x" * 200 + "\nfoo", rules)[0]
        assert_that(cut, contains_string('x..." is one side'))
        assert_that(len(cut) < 300, equal_to(True))


class TestCommand(unittest.TestCase):
    """``pitboss lint contradictions``."""

    def test_exit_codes(self) -> None:
        """Clean is 0, a pair is 1, a bad pairs file or a missing file is 2."""
        both = "You own CI until it is green.\nA red CI is not necessarily you.\n"
        bad = write_text("bad.tsv", "one field\n")
        ran = [
            lint("contradictions", write_text("a.md", "All done.\n")),
            lint("contradictions", write_text("b.md", both)),
            lint("contradictions", write_text("c.md", "x\n"), "--pairs", bad),
            lint("contradictions", "/no/such/file.md"),
        ]
        assert_that([each.code for each in ran], equal_to([0, 1, 2, 2]))
        assert_that(lines(ran[0]), equal_to([f"ok: {DEFAULT_PAIRS} pairs"]))
        assert_that(lines(ran[1]), has_length(2))
        errors = "\n".join(each.err for each in ran[2:])
        assert_that(errors, contains_string("a pair has 5 fields"))
        assert_that(errors, contains_string("/no/such/file.md: No such file"))

    def test_projects_pairs_are_added(self) -> None:
        """A project's pairs are added to the shipped ones; an option drops those."""
        mine, more = map(write_text, ("mine.tsv", "more.tsv"), (PAIRS_FILE, MORE_FILE))
        text = "baar\nfoo\nzed qux\nyou own CI until\nnot necessarily you\n"
        both = write_text("both.md", text)
        options = [
            ["--pairs", mine, "--pairs", more],
            ["--pairs", mine, "--no-default-pairs"],
        ]
        counts = [len(lines(lint("contradictions", both, *each))) for each in options]
        assert_that(counts, equal_to([6, 2]))

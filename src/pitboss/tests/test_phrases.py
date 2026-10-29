"""Tests for the banned-phrase checker and the ``lint text`` command."""

import pathlib
import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length, is_not

from .. import phrases
from . import fakes, world

ATOM_CASES = [
    ("abc", "xxABCxx", True),
    ("a\\sb", "a\tb", True),
    ("a\\db", "a7b", True),
    ("a\\wb", "a_b", True),
    ("\\bcat\\b", "a cat sat", True),
    ("\\bcat\\b", "concatenate", False),
    ("a\\.b", "a.b", True),
    ("a\\.b", "axb", False),
    ("a.b", "a.b", True),
    ("a.b", "axb", False),
    ("ba+r", "baaar", True),
    ("ba+r", "br", False),
    ("ba*r", "br", True),
    ("ba?r", "bar", True),
    ("ba?r", "baar", False),
    ("\\d+", "no digits", False),
    ("[abc]x", "bx", True),
    ("[^abc]x", "bx", False),
    ("[^abc]x", "dx", True),
    ("[\\d\\s]x", " x", True),
    ("[a-c]", "b", False),
    ("[a-c]", "-", True),
    ("[\\.]", ".", True),
    ("[a\\]", "\\", True),
    ("tail\\", "tail\\", True),
    ('"?go"?', 'a "go"', True),
    ("a\\+b", "a+b", True),
]
REFUSED_CASES = [
    ("", "a pattern is empty"),
    ("(a|b)", "a group or an alternation"),
    ("a|b", "a group or an alternation"),
    ("a)", "a group or an alternation"),
    ("?a", "follows no atom"),
    ("a+*", "follows no atom"),
    ("\\b+", "or a word edge"),
    ("[abc", "is not closed"),
    ("[]", "holds no character"),
    ("[^]", "holds no character"),
]
DEFAULT_ROWS = 80
PHRASE_FILE = "# a project's phrases\n\nfoo\tba+r\tbaaar\tSay baz.\n"


def matches(pattern: str, text: str) -> bool:
    """Whether a pattern of the language is found in a text.

    Args:
        pattern: the pattern.
        text: the text.

    Returns:
        Whether it is found.
    """
    return phrases.compile_pattern(pattern).search(text) is not None


def refusal(pattern: str) -> str:
    """The message a pattern is refused with.

    Args:
        pattern: the pattern.

    Returns:
        The message.
    """
    with unittest.TestCase().assertRaises(phrases.PhraseError) as raised:
        phrases.compile_pattern(pattern)
    return str(raised.exception)


def write_text(name: str, text: str) -> str:
    """Write a file in a new directory.

    Args:
        name: the file's name.
        text: its text.

    Returns:
        The file's path.
    """
    path = fakes.directory() / name
    fakes.write(path, text)
    return str(path)


class TestPatterns(unittest.TestCase):
    """The pattern language."""

    def test_atoms(self) -> None:
        """Characters, escapes, classes and quantifiers match as described."""
        found = [matches(pattern, text) for pattern, text, _ in ATOM_CASES]
        assert_that(found, equal_to([expected for _, _, expected in ATOM_CASES]))

    def test_refused_patterns(self) -> None:
        """What the language has not is refused, and the message says why."""
        found = [refusal(pattern) for pattern, _ in REFUSED_CASES]
        for message, (_, expected) in zip(found, REFUSED_CASES, strict=True):
            assert_that(message, contains_string(expected))


class TestParse(unittest.TestCase):
    """Reading a phrase file."""

    def test_parse(self) -> None:
        """Comments and blank lines are skipped; a row gives a phrase."""
        found = phrases.parse(PHRASE_FILE, "mine")
        assert_that(
            [(each.label, each.pattern, each.example, each.instead) for each in found],
            equal_to([("foo", "ba+r", "baaar", "Say baz.")]),
        )

    def test_errors(self) -> None:
        """A line that is no phrase names its file and line."""
        cases = [
            ("a\tb\tc\n", "mine:1: a phrase has 4 fields separated by tabs, this"),
            ("# x\nl\t(a|b)\ta\ti\n", "mine:2: (a|b): '(' is a group"),
            ("l\ta+\tb\ti\n", "mine:1: the example 'b' does not match its pattern"),
        ]
        for text, expected in cases:
            with self.assertRaises(phrases.PhraseError) as raised:
                phrases.parse(text, "mine")
            assert_that(str(raised.exception), contains_string(expected))

    def test_load(self) -> None:
        """A file is read, and a missing file is an error that names it."""
        path = write_text("mine.tsv", PHRASE_FILE)
        assert_that(phrases.load(pathlib.Path(path)), has_length(1))
        missing = pathlib.Path(path).parent / "none.tsv"
        with self.assertRaises(phrases.PhraseError) as raised:
            phrases.load(missing)
        assert_that(str(raised.exception), contains_string(f"{missing}: No such file"))


class TestDefaults(unittest.TestCase):
    """The phrase file pitboss ships."""

    def test_every_example_matches_its_own_pattern(self) -> None:
        """Each row's example is found by its own pattern."""
        found = phrases.parse(phrases.default_text(), "default")
        misses = [each.pattern for each in found if not each.regex.search(each.example)]
        assert_that(misses, equal_to([]))
        assert_that(len(found), equal_to(DEFAULT_ROWS))

    def test_nothing_project_specific(self) -> None:
        """No project's name or ticket number is in the file or the engine."""
        engine = pathlib.Path(phrases.__file__).read_text(encoding="utf-8")
        for text in (phrases.default_text(), engine):
            assert_that(
                re.findall(r"quire|bats|#\d{2,}", text, re.IGNORECASE), equal_to([])
            )


class TestFindings(unittest.TestCase):
    """Searching a text."""

    def test_findings(self) -> None:
        """A finding names the text, the line, the label, the phrase and the advice."""
        banned = phrases.parse(PHRASE_FILE, "mine")
        found = phrases.findings("fine\nsay BAAAR now\n", "t.md", banned)
        assert_that(
            found,
            equal_to(
                [
                    't.md:2: foo: the line "say BAAAR now" holds the phrase'
                    ' "BAAAR", which is refused: Say baz.'
                ]
            ),
        )

    def test_long_lines_are_cut(self) -> None:
        """A long line is shown cut, ending in dots."""
        banned = phrases.parse(PHRASE_FILE, "mine")
        found = phrases.findings("bar " + "x" * 200, "t", banned)
        shown = re.search(r'"(.*)" holds', found[0])
        assert_that(shown is not None and len(shown.group(1)), equal_to(120))

    def test_clean_text(self) -> None:
        """A text with no phrase has no finding."""
        banned = phrases.parse(PHRASE_FILE, "mine")
        assert_that(phrases.findings("nothing here", "t", banned), equal_to([]))


def lint(*argv: str) -> world.Result:
    """Run ``pitboss lint``.

    Args:
        *argv: the arguments after ``lint``.

    Returns:
        What it did.
    """
    return world.invoke(world.make_world(), "lint", *argv)


def lines(result: world.Result) -> Sequence[str]:
    """The lines a command printed.

    Args:
        result: what it did.

    Returns:
        Its standard output's lines.
    """
    return result.out.splitlines()


class TestCommand(unittest.TestCase):
    """``pitboss lint text``."""

    def test_clean(self) -> None:
        """A clean file exits 0."""
        clean = write_text("a.md", "All done as written.\n")
        result = lint("text", clean)
        assert_that(
            (result.code, lines(result)),
            equal_to((0, [f"ok: {DEFAULT_ROWS} phrases"])),
        )

    def test_default_phrases_find(self) -> None:
        """A file with a shipped phrase gets a finding for it and exits 1."""
        dirty = write_text("a.md", "fine\nit passed alone\n")
        result = lint("text", dirty)
        assert_that(result.code, equal_to(1))
        assert_that(lines(result), has_length(1))
        assert_that(lines(result)[0], contains_string(f"{dirty}:2: rerun:"))

    def test_findings_of_several_files(self) -> None:
        """Every file is searched and its findings printed."""
        first = write_text("a.md", "frankly\n")
        second = write_text("b.md", "wait and see\n")
        result = lint("text", first, second)
        assert_that(result.code, equal_to(1))
        assert_that(lines(result), has_length(2))

    def test_project_phrases_are_added(self) -> None:
        """A project's file is added to the shipped one; an option drops that."""
        mine = write_text("mine.tsv", PHRASE_FILE)
        more = write_text("more.tsv", "x\tzed\tzed\tNo zed.\n")
        both = write_text("both.md", "baar and zed and frankly\n")
        added = lint("text", both, "--phrases", mine, "--phrases", more)
        alone = lint("text", both, "--phrases", mine, "--no-default-phrases")
        assert_that(len(lines(added)), equal_to(3))
        assert_that(lines(alone), has_length(1))
        assert_that(lines(alone)[0], contains_string("foo:"))

    def test_bad_phrase_file(self) -> None:
        """A phrase file that is not well formed is a usage error."""
        bad = write_text("bad.tsv", "one field\n")
        text = write_text("a.md", "x\n")
        result = lint("text", text, "--phrases", bad)
        assert_that((result.code, result.out), equal_to((2, "")))
        assert_that(result.err, contains_string("a phrase has 4 fields"))

    def test_missing_text_file(self) -> None:
        """A text file that cannot be read is a usage error naming it."""
        result = lint("text", "/no/such/file.md")
        assert_that(result.code, equal_to(2))
        assert_that(result.err, contains_string("/no/such/file.md: No such file"))

    def test_no_files(self) -> None:
        """The files are required."""
        result = lint("text")
        assert_that(result.code, is_not(equal_to(0)))

    def test_files_not_utf8(self) -> None:
        """A text file or a phrase file that is not UTF-8 is a usage error."""
        text = fakes.directory() / "bad.md"
        text.write_bytes(b"caf\xe9\n")
        table = fakes.directory() / "bad.tsv"
        table.write_bytes(b"a\tb\tc\xff\td\n")
        fine = write_text("a.md", "x\n")
        ran = [
            (text, lint("text", str(text))),
            (table, lint("text", fine, "--phrases", str(table))),
        ]
        for path, outcome in ran:
            assert_that((outcome.code, outcome.out), equal_to((2, "")))
            assert_that(outcome.err, contains_string(f"{path}: not valid UTF-8"))

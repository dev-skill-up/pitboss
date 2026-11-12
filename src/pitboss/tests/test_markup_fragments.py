"""A cut line that no longer reads as a whole is a finding (pitboss#358)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import markuplines


def hunk(old: Sequence[str], new: Sequence[str]) -> str:
    """A ``git diff -U0`` patch of one hunk of ``a.md``.

    Args:
        old: the removed lines.
        new: the added lines.

    Returns:
        The patch.
    """
    rows = [f"-{each}" for each in old] + [f"+{each}" for each in new]
    head = "diff --git a/a.md b/a.md\n--- a/a.md\n+++ b/a.md\n@@ -1 +1 @@\n"
    return head + "".join(f"{each}\n" for each in rows)


REFUSED = {
    "starts mid-sentence": (
        "All of the files, nobody guesses which files a",
        "nobody guesses which files a",
    ),
    "starts with a closing mark": (
        "The NEXT list. The kind is the step alone.",
        ". The kind is the step alone.",
    ),
    "starts with a closing mark ": (
        "Head: lines). The sweep prints",
        "). The sweep prints",
    ),
    "is a table row that lost its edge": ("| a | b | c |", "| a | b"),
    "has an unclosed bracket": ("see (the NEXT list) here", "see (the list here"),
    "has an unclosed backtick": ("see `the NEXT list` here", "see `the list here"),
    "lost the end of its sentence": (
        "It is read first, and then the NEXT list.",
        "It is read first, and then the",
    ),
}
ACCEPTED = {
    "a span cut from the middle": (
        "keep one, cut two, keep three",
        "keep one, keep three",
    ),
    "a row cut inside a cell": ("| a | bbb | c |", "| a | b | c |"),
    "a sentence cut whole": ("It is read. Then the NEXT list.", "It is read."),
    "a sentence reflowed to end its line": (
        "the body saved to a file named Head: lines). The sweep prints",
        "the body saved to a file). The sweep prints",
    ),
    "a line cut to nothing": ("a span", ""),
}


def said(old: str, new: str) -> Sequence[str]:
    """The findings of a patch that changes one line to another.

    Args:
        old: the removed line.
        new: the added line.

    Returns:
        The findings.
    """
    return markuplines.findings("1\t1\ta.md\0", hunk([old], [new]))


class TestDanglingFragments(unittest.TestCase):
    """What a cut may not leave, and the nearest cuts that are fine."""

    def test_each_fragment_is_refused_and_named_with_its_line(self) -> None:
        """Done-when: the finding names the file, the line and what is wrong."""
        for why, (old, new) in REFUSED.items():
            with self.subTest(why):
                found = said(old, new)
                assert_that(found, has_length(1))
                assert_that(found[0], contains_string("a.md` line 1 is a cut line"))
                assert_that(found[0], contains_string(why.strip()))

    def test_t406_every_closing_mark_is_refused_and_an_opening_one_is_not(self) -> None:
        """Each of ``.,;:!?`` and a mark of category Pe and Pf, named with its line."""
        closing = list(".,;:!?") + [")", "]", "}", "\u300d", "\u00bb", "\u201d"]
        for mark in closing:
            with self.subTest(mark):
                found = said("The NEXT list " + mark + " the kind", mark + " the kind")
                assert_that(found, has_length(1))
                assert_that(found[0], contains_string("a.md` line 1 is a cut line"))
                assert_that(found[0], contains_string("starts with a closing mark"))
        opening = said("The NEXT list (the kind", "(the kind")
        assert_that(opening, equal_to([]))

    def test_the_nearest_cuts_that_read_as_a_whole_are_accepted(self) -> None:
        """The nearest inputs: the same kinds of cut, whole."""
        for name, (old, new) in ACCEPTED.items():
            with self.subTest(name):
                assert_that(said(old, new), equal_to([]))

    def test_a_deleted_line_is_no_fragment(self) -> None:
        """A removal leaves nothing."""
        assert_that(markuplines.fragments(hunk(["a line."], [])), equal_to([]))

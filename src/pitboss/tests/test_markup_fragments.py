"""A cut line that no longer reads as a whole is a finding (pitboss#358)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import markuplines
from .test_markup_lines import counted, hunk


def said(old: str, new: str) -> list[str]:
    """The findings of a patch that changes one line to another.

    Args:
        old: the removed line.
        new: the added line.

    Returns:
        The findings.
    """
    return list(markuplines.findings("1\t1\ta.md\0", hunk([old], [new])))


class TestDanglingFragments(unittest.TestCase):
    """What a cut may not leave."""

    def test_a_whole_line_made_of_the_rest_of_a_cut_sentence_is_refused(self) -> None:
        """The first line of a paragraph that now starts mid-sentence."""
        found = said(
            "All of the files, nobody guesses which files a",
            "nobody guesses which files a",
        )
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("a.md` line 1"))
        assert_that(found[0], contains_string("starts mid-sentence"))

    def test_a_line_that_starts_with_a_closing_mark_is_refused(self) -> None:
        """`. The kind is the step alone.`"""
        found = said(
            "The NEXT list. The kind is the step alone.",
            ". The kind is the step alone.",
        )
        assert_that(found[0], contains_string("starts with a closing mark"))

    def test_a_table_row_that_lost_its_edge_is_refused(self) -> None:
        """Half a row."""
        found = said("| a | b | c |", "| a | b")
        assert_that(found[0], contains_string("table row"))

    def test_a_row_cut_inside_a_cell_is_accepted(self) -> None:
        """The nearest input: the edges are there."""
        assert_that(said("| a | bbb | c |", "| a | b | c |"), equal_to([]))

    def test_an_unclosed_bracket_or_backtick_is_refused(self) -> None:
        """A span lost one of its marks."""
        assert_that(
            said("see (the NEXT list) here", "see (the list here")[0],
            contains_string("unclosed bracket"),
        )
        assert_that(
            said("see `the NEXT list` here", "see `the list here")[0],
            contains_string("unclosed backtick"),
        )

    def test_a_sentence_that_lost_its_end_is_refused(self) -> None:
        """The full stop went with the span."""
        found = said(
            "It is read first, and then the NEXT list.",
            "It is read first, and then the",
        )
        assert_that(found[0], contains_string("lost the end of its sentence"))

    def test_a_clean_cut_of_a_span_is_accepted(self) -> None:
        """The cut keeps a whole sentence."""
        assert_that(
            said("keep one, cut two, keep three", "keep one, keep three"), equal_to([])
        )
        assert_that(counted(hunk(["a red fox."], ["a fox."])), equal_to(0))

    def test_a_deleted_line_is_no_fragment(self) -> None:
        """A removal leaves nothing."""
        assert_that(markuplines.fragments(hunk(["a line."], [])), equal_to([]))

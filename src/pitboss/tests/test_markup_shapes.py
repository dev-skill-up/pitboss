"""The shapes of diff the markup-lines classifier meets (keyword: markup-lines, #343).

The rule's words were tested with one added line for each removed line, both
non-empty. The post-mortem of repository-prototype#684 found that the matcher met
other shapes with no test: a blank added line (the empty string is a subsequence of
every line, so it consumed a removed bullet and was never reported), inserted
markup, nested bullets and an added line with no removed partner. Each shape has a
test here, and the real diff of that pull request is the corpus.
"""

import pathlib
import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import markuplines
from .test_markup_fragments import hunk

CORPUS = pathlib.Path(__file__).with_name("corpus") / "rp684-u0.diff"


def added(old: Sequence[str], new: Sequence[str]) -> Sequence[str]:
    """The numbers of the lines named by the added-line findings of a patch.

    Args:
        old: the removed lines.
        new: the added lines.

    Returns:
        The line numbers named, as text.
    """
    found: list[str] = []
    for each in markuplines.added_lines(hunk(old, new)):
        found += re.findall(r" line (\d+) is", each)
    return found


ONE = "- one bullet."
TWO = "- two bullet."
CUT_ONE = "- one bullet"
CUT_TWO = "- two bullet"


class TestShapes(unittest.TestCase):
    """Each shape of added line is judged by itself."""

    def test_a_blank_added_line_is_an_added_line(self) -> None:
        """It is reported, and it does not consume the removed line."""
        assert_that(added([ONE, TWO], ["", CUT_ONE, CUT_TWO]), equal_to(["1"]))

    def test_a_blank_line_between_cut_bullets_is_reported_and_the_cuts_pair(
        self,
    ) -> None:
        """Only the blank line is found; the cuts are still removals."""
        assert_that(added([ONE, TWO], [CUT_ONE, "", CUT_TWO]), equal_to(["2"]))

    def test_blank_lines_at_the_start_and_end_of_a_list(self) -> None:
        """A blank first and a blank last are two added lines."""
        assert_that(added([ONE], ["", CUT_ONE, ""]), equal_to(["1", "3"]))

    def test_a_whitespace_only_added_line_is_an_added_line(self) -> None:
        """Spaces are no cut of a line."""
        assert_that(added([ONE], ["   "]), equal_to(["1"]))

    def test_a_bold_title_on_the_first_and_the_last_bullet_is_refused(self) -> None:
        """Inserted markup is an insertion; the text says what to do instead."""
        old = ["- first step.", "- last step."]
        first = ["- **First**: first step.", "- last step."]
        last = ["- first step.", "- **Last**: last step."]
        for new in (first, last):
            found = markuplines.added_lines(hunk(old, new))
            assert_that(len(found), equal_to(1))
            assert_that(found[0], contains_string("cut characters from the line"))
            assert_that(found[0], contains_string("help text"))

    def test_nested_bullets_pair_by_text_not_by_depth(self) -> None:
        """A nested bullet that loses its tail is a cut; one that gains text is not."""
        old = ["- top bullet.", "  - nested bullet here."]
        assert_that(added(old, ["- top bullet", "  - nested bullet"]), equal_to([]))
        longer = ["- top bullet.", "  - nested bullet here. More"]
        assert_that(added(old, longer), equal_to(["2"]))

    def test_an_added_line_with_no_removed_partner_is_found(self) -> None:
        """A hunk of additions only."""
        assert_that(added([], ["a new line", "another"]), equal_to(["1", "2"]))

    def test_cuts_pair_in_order_and_each_removed_line_once(self) -> None:
        """Two added lines cannot both be the cut of one removed line."""
        assert_that(added(["abcdef"], ["abc", "def"]), equal_to(["2"]))

    def test_the_count_and_the_lines_agree_for_a_blank_line(self) -> None:
        """The numstat says two added lines; the cut is not counted, the blank is."""
        text = hunk([ONE], ["", ONE])
        found = markuplines.findings("2\t1\ta.md\0", text)
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string("gets 1 added line"))


class TestCorpus(unittest.TestCase):
    """The real diff of repository-prototype#684 (ruling steps), at -U0."""

    def test_only_the_blank_line_it_added_is_found(self) -> None:
        """The diff cuts bullets and joins them: one blank line is added at line 49."""
        text = CORPUS.read_text()
        found = markuplines.added_lines(text)
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string("`CLAUDE.md` line 49 is an added line"))
        assert_that(markuplines.fragments(text), equal_to([]))

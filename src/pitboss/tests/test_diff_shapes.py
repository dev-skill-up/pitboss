"""Shapes of input to each classifier of diff lines or markup (keyword: markup-lines).

The post-mortem of repository-prototype#684: a classifier tested with the rule's
words alone met inputs of another shape. Each classifier that reads a diff or a
markup claim has its odd shapes here: a deleted file, a mode change, a quoted
path, a binary file, a missing final newline, blank and comment rows, a claim
split over lines and in another case, and markers that differ in case.
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import lintchange, markercheck, markupclaim, markuplines

PLAIN = "diff --git a/a.md b/a.md\n--- a/a.md\n+++ b/a.md\n@@ -1 +1 @@\n-x\n+y\n"


def paths(patch: str) -> Sequence[str]:
    """The paths of the hunks of a patch.

    Args:
        patch: the output of ``git diff -U0``.

    Returns:
        One path for each hunk.
    """
    return [name for name, _, _ in markuplines.hunks(patch)]


class TestHunks(unittest.TestCase):
    """``markuplines.hunks`` reads every shape of file header."""

    def test_a_deleted_file_has_no_hunk_to_read(self) -> None:
        """``+++ /dev/null`` names no path; its rows are removals only."""
        gone = (
            "diff --git a/a.md b/a.md\n--- a/a.md\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
        )
        assert_that(paths(gone), equal_to([]))

    def test_a_mode_change_and_a_binary_file_have_no_hunk(self) -> None:
        """No ``@@`` line, so nothing is read."""
        mode = "diff --git a/a.md b/a.md\nold mode 100644\nnew mode 100755\n"
        binary = "diff --git a/a.png b/a.png\nBinary files a/a.png and b/a.png differ\n"
        assert_that(paths(mode + binary), equal_to([]))

    def test_a_quoted_path_with_a_space_or_unicode(self) -> None:
        """A path git quotes is unquoted; one with a space is kept whole."""
        names = {"b/a b.md": "a b.md", '"b/caf\\303\\251 a.md"': "caf\u00e9 a.md"}
        for written, read in names.items():
            with self.subTest(written):
                assert_that(paths(PLAIN.replace("b/a.md", written)), equal_to([read]))

    def test_hunks_of_two_files_and_a_missing_final_newline(self) -> None:
        """Each hunk of each file is read; a missing final newline adds no line."""
        second = PLAIN.replace("a.md", "b.md") + "@@ -9 +9 @@\n-p\n+q\n"
        cut = PLAIN.replace("-x\n+y", "-xy\n+x") + "\\ No newline at end of file\n"
        found = (paths(PLAIN + second), markuplines.added_lines(cut))
        assert_that(found, equal_to((["a.md", "b.md", "b.md"], [])))


class TestLintChange(unittest.TestCase):
    """``lintchange.changed_lines`` counts the code rows of a hunk."""

    def test_blank_and_comment_rows_are_no_code(self) -> None:
        """Only a row with code counts as a change."""
        rows = "+\n+# note\n+x = 1\n-\n-# gone\n-y = 2"
        found = lintchange.changed_lines(10, rows)
        assert_that([line for line, _ in found], equal_to([12, 13]))

    def test_a_hunk_that_only_removes_is_a_deletion(self) -> None:
        """A docstring there is no change (``in_place`` is false)."""
        assert_that(lintchange.changed_lines(4, "-x = 1"), equal_to([(4, False)]))

    def test_a_missing_newline_row_is_ignored(self) -> None:
        """The marker row has no sign."""
        found = lintchange.changed_lines(3, "+x = 1\n\\ No newline at end of file")
        assert_that(found, equal_to([(3, True)]))


def said(text: str) -> int:
    """How many findings a body gets for a changed .md file.

    Args:
        text: the body.

    Returns:
        The number.
    """
    return len(markupclaim.findings(f"## Plan\n\n{text}\n", ["a.md"]))


class TestMarkupClaim(unittest.TestCase):
    """``markupclaim.findings`` reads a sentence in any layout."""

    def test_each_layout_of_a_sentence(self) -> None:
        """Case and a line break hide no claim; another subject is no claim."""
        cases = {
            "NO .md or .rst file\nwas changed.": 1,
            "No markdown file has been edited.": 1,
            "No .py file is changed.": 0,
            "One .md file is changed.": 0,
        }
        for text, count in cases.items():
            with self.subTest(text):
                assert_that(said(text), equal_to(count))

    def test_no_markup_in_the_diff_means_no_finding(self) -> None:
        """The claim is true when the diff changes none."""
        found = markupclaim.findings("## Plan\n\nNo .md file is changed.\n", ["a.py"])
        assert_that(found, equal_to([]))


class TestMarkerCheck(unittest.TestCase):
    """``markercheck.errors`` compares sets exactly."""

    def test_empty_sets_agree_and_case_is_a_difference(self) -> None:
        """Nothing printed and nothing named is no error; a case change is two."""
        assert_that(markercheck.errors(set(), set(), set()), equal_to([]))
        found = markercheck.errors({"HOLD"}, set(), {"hold"})
        assert_that(len(found), equal_to(2))

    def test_a_self_explained_marker_needs_no_name_but_a_name_needs_a_print(
        self,
    ) -> None:
        """Both directions."""
        assert_that(markercheck.errors({"A"}, {"A"}, set()), equal_to([]))
        assert_that(len(markercheck.errors(set(), {"A"}, {"A"})), equal_to(1))

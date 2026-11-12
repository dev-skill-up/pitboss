"""A9 and A25: what a review asks for a documentation cut and an extra file.

A9 (owner, 2026-11-08 23:47Z): no piecemeal "makes false" or "depends on a cut
passage" rounds; the whole section is cut in one pass. A25 (owner, 2026-11-11
11:00Z): an extra file found in review is removed and gets a ``.gitignore`` line.
"""

import unittest

from hamcrest import assert_that, contains_string, empty, has_length

from .. import extrafile, reviewrules
from .linting import HEAD, lint, write_text

REVIEW = (
    f"## Review\nReviewed: {HEAD}\nPlan: approved\nExecution: approved\n"
    "Verdict: approved\n"
)


def linted(finding: str) -> str:
    """What ``lint review`` printed for a review with one more line.

    Args:
        finding: the line.

    Returns:
        Its standard output.
    """
    return lint("review", write_text("review.md", REVIEW + finding + "\n")).out


class TestPiecemeal(unittest.TestCase):
    """A documentation cut is asked for a whole section at a time."""

    def test_a9_a_cut_of_one_sentence_is_refused(self) -> None:
        """Pitboss 470: one sentence of a doc, then the next, round after round."""
        found = reviewrules.piecemeal_findings("doc/flow.rst: cut the second sentence.")
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("cut it in one pass"))

    def test_a9_a_passage_that_depends_on_a_cut_one_is_refused(self) -> None:
        """The words of the rule: depends on a cut passage."""
        said = "The README.md paragraph depends on a cut passage."
        assert_that(reviewrules.piecemeal_findings(said), has_length(1))

    def test_a9_a_whole_section_cut_is_not_piecemeal(self) -> None:
        """The nearest inputs it must still accept: a section, and a code line."""
        for said in (
            "doc/flow.rst: cut the whole section `Old flow` in one pass.",
            "src/pitboss/flow.py: remove the line that sets the label.",
        ):
            with self.subTest(said=said):
                assert_that(reviewrules.piecemeal_findings(said), empty())

    def test_a9_the_review_lint_refuses_the_round(self) -> None:
        """``pitboss lint review`` prints the finding."""
        out = linted("doc/flow.rst: trim the last clause of the paragraph.")
        assert_that(out, contains_string("review-piecemeal: line 6"))


class TestExtraFile(unittest.TestCase):
    """An extra file gets its step."""

    def test_a25_an_extra_file_without_the_step_is_refused(self) -> None:
        """Pitboss 468: the file was deleted and came back."""
        found = extrafile.findings("An extra file `out.json` is in the PR.")
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string(extrafile.STEP))

    def test_a25_an_extra_file_with_the_step_passes(self) -> None:
        """The nearest input it must still accept."""
        said = f"Stray file `out.json`: {extrafile.STEP}."
        assert_that(extrafile.findings(said), empty())

    def test_a25_a_line_that_names_no_extra_file_passes(self) -> None:
        """Only an extra file needs the step."""
        assert_that(extrafile.findings("The file `a.py` is right."), empty())

    def test_a25_the_review_lint_refuses_it(self) -> None:
        """``pitboss lint review`` prints the finding."""
        out = linted("A scratch file `tmp.txt` was committed.")
        assert_that(out, contains_string("review-extra-file: line 6"))

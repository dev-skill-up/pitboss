"""A note that names a case the change does not handle is a finding (#240)."""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, reviewnote, shapes
from .briefmake import text
from .test_commands import sweep
from .test_evidence_rules import words
from .test_flow_sweep import APPROVED, CHANGES, graded, world_with
from .briefmake import EXECUTION_REVIEWS

BRIEF_SENTENCE = (
    "a gap against the goal or the Done-when that you can name (a case, a"
    " fixture, a repository kind the change does not handle) is a finding, never"
    " a note; a note holds only what the change did not cause."
)
MISSED_NOTE = (
    "Notes: the line reads open PRs only, so rulings on merged PRs are missed."
)
PLAIN_NOTE = "Notes: the wording could be shorter."
LINE = "REVIEW NOTE owner/project#3"


def noted(note: str, execution: str = APPROVED) -> shapes.Comment:
    """A review of PR 3 with a ``Notes`` paragraph.

    Args:
        note: the paragraph.
        execution: its Execution grade.

    Returns:
        The comment.
    """
    review = graded(APPROVED, execution, 1)
    return dataclasses.replace(review, body=review.body + "\n" + note + "\n")


def printed(note: str, execution: str = APPROVED) -> bool:
    """Whether the sweep prints the line for a PR whose review has the note.

    Args:
        note: the paragraph.
        execution: the Execution grade of the review.

    Returns:
        True when the line is printed.
    """
    return LINE in sweep(world_with([noted(note, execution)])).out


class TestBriefsAndRules(unittest.TestCase):
    """Done-when 1 and 2: the review briefs say it."""

    def test_the_full_and_the_execution_review_carry_the_sentence(self) -> None:
        """REVIEW_FULL and REVIEW_EXECUTION pin it; the scoped briefs have none."""
        found = {kind: BRIEF_SENTENCE in words(text(kind)) for kind in brief.Kind}
        assert_that(
            sorted(kind.name for kind, has in found.items() if has),
            equal_to(sorted(kind.name for kind in EXECUTION_REVIEWS)),
        )


class TestParagraph(unittest.TestCase):
    """The Notes paragraph and its words."""

    def test_each_word_is_a_gap(self) -> None:
        """The four words, in any case."""
        for word in ("missed", "never counted", "not handled", "only", "Only"):
            body = f"Verdict: x\n\nNotes: a case is {word} here\n"
            assert_that(reviewnote.gap(body), contains_string(word))

    def test_where_the_paragraph_starts_and_ends(self) -> None:
        """A heading, a blank line before the text, the next heading."""
        paragraphs = {
            "## Notes\nfirst\nsecond only\n\nafter missed\n": "first second only",
            "## Notes\n\nlater missed\n\nafter\n": "later missed",
            "Notes:\nfine\n## Other\nmissed\n": "fine",
            "Verdict: x\n": "",
        }
        for body, wanted in paragraphs.items():
            assert_that(reviewnote.paragraph(body), equal_to(wanted))

    def test_the_words_outside_the_paragraph_do_not_count(self) -> None:
        """A finding line with the word is not a note."""
        body = "Missed earlier: x\nonly this\n\nNotes: fine\n"
        assert_that(reviewnote.gap(body), equal_to(""))


class TestSweep(unittest.TestCase):
    """Done-when 3: REVIEW NOTE is printed, or not."""

    def test_a_note_that_names_a_missed_case_prints_the_line(self) -> None:
        """The line names the PR and quotes the note."""
        swept = sweep(world_with([noted(MISSED_NOTE)])).out
        assert_that(swept, contains_string(LINE))
        assert_that(swept, contains_string("rulings on merged PRs are missed"))

    def test_a_note_that_names_no_case_prints_none(self) -> None:
        """A plain note, and a review with no note."""
        assert_that(printed(PLAIN_NOTE), equal_to(False))
        plain = world_with([graded(APPROVED, APPROVED, 1)])
        assert_that(LINE in sweep(plain).out, equal_to(False))

    def test_a_review_that_asks_for_changes_prints_none(self) -> None:
        """Only an approved PR gets the line."""
        assert_that(printed(MISSED_NOTE, CHANGES), equal_to(False))

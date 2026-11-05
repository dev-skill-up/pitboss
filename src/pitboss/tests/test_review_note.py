"""A note that names a case the change does not handle is a finding (#240)."""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, reviewnote, shapes
from .briefmake import has_none, pinned, text
from .test_commands import sweep
from .test_evidence_rules import read, words
from .test_flow_sweep import APPROVED, graded, world_with

BRIEF_SENTENCE = (
    "a gap against the goal or the Done-when that you can name (a case, a"
    " fixture, a repository kind the change does not handle) is a finding, never"
    " a note; a note holds only what the change did not cause."
)
RULES_BULLET = (
    "before merging, read the Notes of the newest review (pitboss#240, keyword:"
    " review-note): a note that names a case of the goal the change does not"
    " handle is a finding and starts a fix round, not a ticket"
)
MISSED_NOTE = (
    "Notes: the line reads open PRs only, so rulings on merged PRs are missed.\n"
)
PLAIN_NOTE = "Notes: the wording could be shorter.\n"
LINE = "REVIEW NOTE owner/project#3"


def noted(note: str) -> shapes.Comment:
    """An approving review of PR 3 with a ``Notes`` paragraph.

    Args:
        note: the paragraph.

    Returns:
        The comment.
    """
    review = graded(APPROVED, APPROVED, 1)
    return dataclasses.replace(review, body=review.body + "\n" + note)


class TestBriefs(unittest.TestCase):
    """Done-when 1: the review briefs say it."""

    def test_the_full_and_the_execution_review_carry_the_sentence(self) -> None:
        """REVIEW_FULL and REVIEW_EXECUTION pin it."""
        for kind in (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION):
            assert_that(words(text(kind)), contains_string(BRIEF_SENTENCE))

    def test_the_scoped_briefs_do_not(self) -> None:
        """A scoped review reads nothing outside its scope."""
        for kind in (brief.Kind.REVIEW_FIX_ROUND, brief.Kind.REVIEW_RELOCK):
            has_none(text(kind), ["Notes:"])
        pinned(brief.Kind.REVIEW_FULL, ["Notes: a gap"])


class TestRules(unittest.TestCase):
    """Done-when 2: the merge step of the orchestrator's rules."""

    def test_the_merge_step_reads_the_notes_of_the_newest_review(self) -> None:
        """The bullet sits in Agents and slots."""
        rules = read("rules.md")
        start = rules.index("\n## Agents and slots\n")
        section = rules[start + 1 :].split("\n## ")[0]
        assert_that(words(section), contains_string(RULES_BULLET))


class TestParagraph(unittest.TestCase):
    """The Notes paragraph and its words."""

    def test_each_word_is_a_gap(self) -> None:
        """The four words, in any case."""
        for word in ("missed", "never counted", "not handled", "only", "Only"):
            body = f"Verdict: x\n\nNotes: a case is {word} here\n"
            assert_that(reviewnote.gap(body), contains_string(word))

    def test_a_heading_and_the_lines_below_it_are_the_paragraph(self) -> None:
        """The paragraph ends at the blank line."""
        body = "## Notes\nfirst\nsecond only\n\nafter missed\n"
        assert_that(reviewnote.paragraph(body), equal_to("first second only"))

    def test_the_words_outside_the_paragraph_do_not_count(self) -> None:
        """A finding line with the word is not a note."""
        body = "Missed earlier: x\nonly this\n\nNotes: fine\n"
        assert_that(reviewnote.gap(body), equal_to(""))

    def test_no_notes_is_empty(self) -> None:
        """No paragraph, nothing."""
        assert_that(reviewnote.paragraph("Verdict: x\n"), equal_to(""))

    def test_a_bare_heading_takes_the_text_after_a_blank_line(self) -> None:
        """Nothing is found yet, so the blank line does not end it."""
        body = "## Notes\n\nlater missed\n\nafter\n"
        assert_that(reviewnote.paragraph(body), equal_to("later missed"))

    def test_a_heading_ends_the_paragraph(self) -> None:
        """The next heading closes it."""
        body = "Notes:\nfine\n## Other\nmissed\n"
        assert_that(reviewnote.paragraph(body), equal_to("fine"))


class TestSweep(unittest.TestCase):
    """Done-when 3: REVIEW NOTE is printed, or not."""

    def test_a_note_that_names_a_missed_case_prints_the_line(self) -> None:
        """The line names the PR and quotes the note."""
        swept = sweep(world_with([noted(MISSED_NOTE)])).out
        assert_that(swept, contains_string(LINE))
        assert_that(swept, contains_string("rulings on merged PRs are missed"))

    def test_a_note_that_names_no_case_prints_none(self) -> None:
        """A plain note, and a review with no note."""
        assert_that(LINE in sweep(world_with([noted(PLAIN_NOTE)])).out, equal_to(False))
        plain = world_with([graded(APPROVED, APPROVED, 1)])
        assert_that(LINE in sweep(plain).out, equal_to(False))

    def test_a_review_that_asks_for_changes_prints_none(self) -> None:
        """Only an approved PR gets the line."""
        review = graded(APPROVED, "changes needed", 1)
        asking = dataclasses.replace(review, body=review.body + MISSED_NOTE)
        assert_that(LINE in sweep(world_with([asking])).out, equal_to(False))

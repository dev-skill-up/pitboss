"""A note that names a case the change does not handle is a finding (#240)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, reviewnote
from .briefmake import text
from .test_evidence_rules import words
from .briefmake import EXECUTION_REVIEWS

BRIEF_SENTENCE = (
    "a gap against the goal or the Done-when that you can name (a case, a"
    " fixture, a repository kind the change does not handle) is a finding, never"
    " a note; a note holds only what the change did not cause."
)


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

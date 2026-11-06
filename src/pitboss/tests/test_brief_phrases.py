"""No brief holds a phrase that ``pitboss lint text`` refuses (pitboss#272).

A reviewer reuses the wording of its brief, and the target repository's lint
refuses these phrases in a review comment, so the brief must never say them.
"""

import unittest

from hamcrest import assert_that, equal_to

from .. import brief, brieftext, brieftextci, brieftextlint, brieftextwork, phrases
from . import briefmake

BANNED = phrases.parse(phrases.default_text(), "phrases.tsv")
SENTENCES = [
    (f"{module.__name__}.{name}", value)
    for module in (brieftext, brieftextci, brieftextlint, brieftextwork)
    for name, value in sorted(vars(module).items())
    if isinstance(value, str) and name.isupper()
]


class TestBriefsHoldNoRefusedPhrase(unittest.TestCase):
    """What the briefs say is what the lint accepts."""

    def test_no_brief_of_any_kind_holds_a_refused_phrase(self) -> None:
        """Each kind of brief, as the sweep prints it."""
        found = [
            finding
            for kind in brief.Kind
            for finding in phrases.findings(briefmake.text(kind), kind.name, BANNED)
        ]
        assert_that(found, equal_to([]))

    def test_no_sentence_of_the_brief_texts_holds_a_refused_phrase(self) -> None:
        """Each sentence, whether or not a kind of brief uses it."""
        found = [
            finding
            for name, sentence in SENTENCES
            for finding in phrases.findings(sentence, name, BANNED)
        ]
        assert_that(found, equal_to([]))

    def test_the_sentences_are_read(self) -> None:
        """The scan reads the sentences, so an empty scan is no pass."""
        assert_that(len(SENTENCES) > 20, equal_to(True))

    def test_the_scan_finds_the_word_that_started_it(self) -> None:
        """A sentence with the word `honest` is found."""
        found = phrases.findings("a failure an honest worker could hit", "x", BANNED)
        assert_that(len(found), equal_to(1))

"""An impossibility cites the rulings it rests on, in exact words (pitboss#487).

The keyword is impossible-cites. Moshe, 2026-11-22 02:09Z: "impossibility should
either be conflict between ruling and reality or two or more rulings, and they
should cite exact words."
"""

import unittest

from hamcrest import assert_that, equal_to

from .. import impossiblecites
from . import refused
from .says import says
from .test_handback_pause import IMPOSSIBLE, RULING, made, run

REGISTER_WORDS = "An approved Plan is never edited"
OPUS_WORDS = "do these steps"
OPUS = {"body": f"Opus ruling\nRuling: {OPUS_WORDS}\n"}


def _cites(*words: str) -> str:
    quoted = [f'Cites: "{each}"' for each in words]
    return _alone(IMPOSSIBLE) + "\n".join(quoted) + "\n"


def _alone(text: str) -> str:
    # the hand-back with the citation line the shared text carries taken out
    return impossiblecites.CITE.sub("", text)


def _refused(text: str, why: str) -> None:
    # the filing is refused for ``why`` and nothing is changed on the PR
    here = made([RULING])
    done = run(here, text)
    says(done.err, why)
    assert_that((done.code, refused.changes(here)), equal_to((2, [])))


class TestCitations(unittest.TestCase):
    """What a filing must cite."""

    def test_a_filing_with_no_cited_ruling_is_refused(self) -> None:
        """No ``Cites`` line."""
        _refused(_alone(IMPOSSIBLE), "cites no ruling")

    def test_words_that_are_no_ruling_are_refused(self) -> None:
        """A quote that is in neither the register nor the PR's ruling."""
        _refused(_cites("the worker's own wording"), "no ruling of the register")

    def test_one_real_quote_with_one_that_is_no_ruling_is_refused(self) -> None:
        """The nearest input to an accepted filing: one quote of it is changed."""
        near = REGISTER_WORDS.replace("never", "always")
        _refused(_cites(REGISTER_WORDS, near), "no ruling of the register")

    def test_a_cited_conflict_is_accepted(self) -> None:
        """One ruling of the register, and two: a rule and the PR's own ruling."""
        one = made([RULING])
        two = made([OPUS])
        assert_that(run(one, _cites(REGISTER_WORDS)).code, equal_to(0))
        assert_that(run(two, _cites(REGISTER_WORDS, OPUS_WORDS)).code, equal_to(0))

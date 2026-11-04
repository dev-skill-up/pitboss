"""The skill says the orchestrator never sits in a long wait (pitboss#178)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .test_evidence_rules import read, words

FILE = "rules.md"
PHRASES = (
    "The orchestrator never sits in a long wait",
    "never holds a blocking wait (`sleep`, `Monitor`, a wait on a task) for a worker or a CI run",
    "a worker's long run is the worker's own, started in the background with a log",
)


def missing(text: str) -> Sequence[str]:
    """The phrases the rules file does not hold.

    Args:
        text: the file's text.

    Returns:
        A finding for each phrase missing.
    """
    return [f"{FILE}: no `{phrase}`" for phrase in PHRASES if phrase not in words(text)]


class TestOrchestratorWait(unittest.TestCase):
    """The rules state the wait rule for the orchestrator and for its workers."""

    def test_the_skill_says_it(self) -> None:
        """The rules hold the orchestrator's rule and the worker's."""
        assert_that(missing(read(FILE)), equal_to([]))

    def test_each_phrase_is_needed(self) -> None:
        """Dropping a phrase makes the check name that phrase."""
        for phrase in PHRASES:
            with self.subTest(phrase):
                found = missing(words(read(FILE)).replace(phrase, ""))
                assert_that(len(found), equal_to(1))
                assert_that(found[0], contains_string(phrase))

"""The hand-back has a ``Deviations:`` line (keyword: deviations, pitboss#257)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftextnote, brieftextwork, deviations
from . import fakes, world
from .briefmake import text
from .test_evidence_rules import read, words

EXECUTION_REVIEWS = {brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION}
WORKERS = (
    brief.Kind.NEW_PR,
    brief.Kind.FIRST_ROUND,
    brief.Kind.REVISE_PLAN,
    brief.Kind.FIX_REVIEW,
    brief.Kind.FIX_CI,
    brief.Kind.RESOLVE_CONFLICT,
    brief.Kind.RULING_STEPS,
    brief.Kind.RULING_AS_GIVEN,
    brief.Kind.RUN_PLAN,
)
ASKS = brieftextwork.DEVIATIONS
READS = brieftextnote.DEVIATIONS_REVIEW
WITH_LINE = "PR 5\nhead abc\nDeviations: two `sed -i` runs, one `rm`\n"
WITH_NONE = "PR 5\nhead abc\nDeviations: none\n"
WITHOUT_LINE = "PR 5\nhead abc\nI used the Edit tool.\n"
EMPTY_LINE = "PR 5\nDeviations:\n"


def saved(handback: str) -> str:
    """Save a hand-back to a file.

    Args:
        handback: the hand-back text.

    Returns:
        The file's name.
    """
    path = fakes.directory() / "handback.txt"
    path.write_text(handback, encoding="utf-8")
    return path.as_posix()


class TestTheBriefs(unittest.TestCase):
    """A worker is asked for the line, a reviewer reads it."""

    def test_every_worker_brief_asks_for_the_line_before_the_hand_back(self) -> None:
        """The sentence is in each worker brief, and no review has it."""
        for kind in WORKERS:
            found = text(kind)
            assert_that(found, contains_string(ASKS))
            assert_that(found.index(ASKS) < found.index("Hand-back:"), equal_to(True))
        for kind in EXECUTION_REVIEWS:
            assert_that(ASKS in text(kind), equal_to(False))

    def test_the_sentence_says_a_hand_back_without_it_is_not_started(self) -> None:
        """The orchestrator sends it back."""
        assert_that(
            ASKS,
            contains_string("a hand-back without it is NOT STARTED and is sent back"),
        )

    def test_the_review_of_an_execution_reads_the_line_and_records_it(self) -> None:
        """A trace in the tree is a finding, a clean tree never fails."""
        for kind in EXECUTION_REVIEWS:
            assert_that(text(kind), contains_string(READS))
        for kind in (brief.Kind.REVIEW_PLAN, brief.Kind.REVIEW_FIX_ROUND):
            assert_that(READS in text(kind), equal_to(False))
        for part in (
            "only when it left a trace in the tree that the Edit tool would not have",
            "it never fails a PR for a clean tree",
            "for the sweep's ledger line for the worker",
        ):
            assert_that(READS, contains_string(part))

    def test_the_reference_states_the_rule(self) -> None:
        """rules.md has the check of the hand-back and the review."""
        rule = "a hand-back without it is NOT STARTED text the orchestrator sends back"
        assert_that(words(read("rules.md")), contains_string(rule))


class TestTheHandBack(unittest.TestCase):
    """A hand-back with and without the line."""

    def test_the_line_is_read_with_its_text(self) -> None:
        """What follows the prefix, stripped; nothing for no line."""
        assert_that(deviations.line(WITH_LINE), equal_to("two `sed -i` runs, one `rm`"))
        assert_that(deviations.line(WITH_NONE), equal_to("none"))
        assert_that(deviations.line(WITHOUT_LINE), equal_to(""))
        assert_that(deviations.line(EMPTY_LINE), equal_to(""))

    def test_without_the_line_it_is_not_started(self) -> None:
        """Only a line that says something passes."""
        assert_that(deviations.not_started(WITH_LINE), equal_to(""))
        assert_that(deviations.not_started(WITH_NONE), equal_to(""))
        for each in (WITHOUT_LINE, EMPTY_LINE):
            assert_that(deviations.not_started(each), equal_to(deviations.NOT_STARTED))
            assert_that(deviations.NOT_STARTED, contains_string("NOT STARTED"))

    def test_the_command_prints_ok_or_the_text_and_exits_1(self) -> None:
        """The orchestrator's check of a hand-back saved in a file."""
        expected = {
            WITH_LINE: [0, "ok\n"],
            WITH_NONE: [0, "ok\n"],
            WITHOUT_LINE: [1, deviations.NOT_STARTED + "\n"],
        }
        for handback, wanted in expected.items():
            done = world.invoke(world.make_world(), "hand-back-check", saved(handback))
            assert_that([done.code, done.out], equal_to(wanted))

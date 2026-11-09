"""The briefs require a test of the input a new or loosened lint rejects (#180)."""

import unittest

from .. import brief
from .briefmake import has_none, pinned, text
from .test_brief_nox import WORKERS

LINT_TEST = (
    "Lint tests: a lint, check or exemption that is new or loosened ships a test"
    " for the nearest input it must still reject (a form spelled the way the"
    " loosened rule now accepts, such as a fixed sleep whose timer handle is"
    " kept), as well as a test for the input it accepts."
)
LINT_TEST_REVIEW = (
    "Lint tests: a lint, check or exemption that is new or loosened and ships no"
    " test for the nearest input it must still reject is changes needed (a form"
    " spelled the way the loosened rule now accepts, such as a fixed sleep whose"
    " timer handle is kept); a test of the accepted input alone does not show"
    " that the rule still rejects."
)
EXECUTION_REVIEWS = [brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION]
OTHER_REVIEWS = sorted(brief.REVIEWS - set(EXECUTION_REVIEWS), key=lambda k: k.name)


class TestLintTests(unittest.TestCase):
    """The worker briefs carry the rule and the Execution reviews enforce it."""

    def test_every_worker_brief_requires_a_test_for_the_rejected_input(self) -> None:
        """A worker brief carries the sentence; no review brief carries it."""
        for kind in WORKERS:
            pinned(kind, [LINT_TEST])
        for kind in (*EXECUTION_REVIEWS, *OTHER_REVIEWS):
            has_none(text(kind), [LINT_TEST])

    def test_the_execution_reviews_reject_a_lint_without_that_test(self) -> None:
        """The reviews that grade an Execution carry the changes-needed sentence."""
        for kind in EXECUTION_REVIEWS:
            pinned(kind, [LINT_TEST_REVIEW])
        for kind in (*WORKERS, *OTHER_REVIEWS):
            has_none(text(kind), [LINT_TEST_REVIEW])

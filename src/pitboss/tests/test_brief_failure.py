"""The Plan and Execution reviews refuse a hidden failure (pitboss#353)."""

import unittest

from .. import brief
from .briefmake import has_none, pinned, text

FAILURE_REVIEW = (
    "Failures: a change that turns a failing condition (a rejected credential, a"
    " missing input, an error exit) into a green run, a skip, a notice, a warning"
    " or a default is changes needed, whatever the ticket's Done-when allows,"
    " unless the owner's own words quoted in the ticket ask for it."
)
REVIEWS = [
    brief.Kind.REVIEW_FULL,
    brief.Kind.REVIEW_PLAN,
    brief.Kind.REVIEW_EXECUTION,
]
OTHERS = sorted(set(brief.Kind) - set(REVIEWS), key=lambda k: k.name)


class TestFailureReview(unittest.TestCase):
    """The reviews of a Plan and of an Execution carry the sentence."""

    def test_the_plan_review_carries_the_sentence(self) -> None:
        """REVIEW_PLAN prints it."""
        pinned(brief.Kind.REVIEW_PLAN, [FAILURE_REVIEW])

    def test_the_execution_review_carries_the_sentence(self) -> None:
        """REVIEW_EXECUTION prints it."""
        pinned(brief.Kind.REVIEW_EXECUTION, [FAILURE_REVIEW])

    def test_the_full_review_carries_the_sentence(self) -> None:
        """REVIEW_FULL grades both stages and prints it."""
        pinned(brief.Kind.REVIEW_FULL, [FAILURE_REVIEW])

    def test_no_other_brief_carries_the_sentence(self) -> None:
        """A worker brief, a ruling and the scoped reviews do not print it."""
        for kind in OTHERS:
            has_none(text(kind), [FAILURE_REVIEW])

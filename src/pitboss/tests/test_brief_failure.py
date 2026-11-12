"""The Plan and Execution reviews refuse a hidden failure (pitboss#353)."""

import unittest

from .. import brief
from .briefmake import pinned, text
from .says import has_none

SENTENCE = (
    "Failures: a change that turns a failing condition (a rejected credential, a"
    " missing input, an error exit) into a green run, a skip, a notice, a warning"
    " or a default is changes needed, whatever the ticket's Done-when allows,"
    " unless the owner's own words quoted in the ticket ask for it."
)
GRADES_A_PLAN_OR_AN_EXECUTION = {
    brief.Kind.REVIEW_FULL: True,
    brief.Kind.REVIEW_PLAN: True,
    brief.Kind.REVIEW_EXECUTION: True,
}


class TestFailureReview(unittest.TestCase):
    """The reviews of a Plan and of an Execution carry the sentence."""

    def test_each_review_of_a_plan_or_an_execution_prints_it(self) -> None:
        """REVIEW_PLAN, REVIEW_EXECUTION and REVIEW_FULL print it."""
        for kind in GRADES_A_PLAN_OR_AN_EXECUTION:
            pinned(kind, [SENTENCE])

    def test_every_other_brief_leaves_it_out(self) -> None:
        """A worker brief, a ruling and the scoped reviews do not print it."""
        for kind in set(brief.Kind) - set(GRADES_A_PLAN_OR_AN_EXECUTION):
            has_none(text(kind), [SENTENCE])

"""The Plan-writing briefs put the CI-pointer rows last (pitboss#274)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import brief, brieftextci
from .briefmake import has_none, pinned, text

SENTENCE = (
    "Number the Plan rows with every command row first and the CI-pointer rows"
    " last; plan-row pairs the Nth Evidence command with row N (pitboss#274)."
)


class TestPointerRowsLast(unittest.TestCase):
    """A worker who writes a Plan is told the order of its rows."""

    def test_the_sentence_is_the_one_of_the_ticket(self) -> None:
        """The constant is the pinned text."""
        assert_that(brieftextci.PLAN_POINTER_LAST, equal_to(SENTENCE))

    def test_the_brief_for_a_new_pr_carries_it(self) -> None:
        """A new PR writes a Plan."""
        pinned(brief.Kind.NEW_PR, [SENTENCE])

    def test_the_brief_for_a_plan_fix_carries_it(self) -> None:
        """A revised Plan is numbered the same way."""
        pinned(brief.Kind.REVISE_PLAN, [SENTENCE])

    def test_a_brief_that_writes_no_plan_does_not(self) -> None:
        """A CI fix writes no Plan."""
        has_none(text(brief.Kind.FIX_CI), [SENTENCE])

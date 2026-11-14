"""The Plan-writing briefs put the CI-pointer rows last (pitboss#274)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import brief, brieftextci
from .briefmake import pinned, text
from .says import has_none

SENTENCE = (
    "Number the Plan rows with every command row first and the CI-pointer rows"
    " last; plan-row pairs the Nth Evidence command with row N (pitboss#274)."
)


class TestPointerRowsLast(unittest.TestCase):
    """A worker who writes a Plan is told the order of its rows."""

    def test_a_brief_that_writes_no_plan_does_not(self) -> None:
        """A CI fix writes no Plan."""
        has_none(text(brief.Kind.FIX_CI), [SENTENCE])

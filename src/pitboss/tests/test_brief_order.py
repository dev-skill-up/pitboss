"""The briefs carry the rule for a change of a precedence order (#182)."""

import unittest

from hamcrest import assert_that, contains_string

from .. import brief
from .briefmake import has_none, pinned, text
from .test_evidence_rules import read, words

ORDER_TICKET = (
    "Order tables: a ticket or ruling that changes the order in which steps are"
    " offered gives, in its Done-when, a table of the full order (every state"
    " against the step offered) and names a test per row, so that no state is"
    " left to the worker's choice."
)
ORDER_REVIEW = (
    "Order tables: a PR that changes the order in which steps are offered is"
    " changes needed when a doc row (`sweep.md`, `rules.md`, `slots.md`) or the"
    " code differs from the ticket's table of the full order, or when a row of"
    " that table has no named test."
)
REVIEWS = [
    brief.Kind.REVIEW_FULL,
    brief.Kind.REVIEW_PLAN,
    brief.Kind.REVIEW_EXECUTION,
]
OTHERS = sorted(
    set(brief.Kind) - set(REVIEWS) - {brief.Kind.RULING}, key=lambda k: k.name
)


class TestOrderTables(unittest.TestCase):
    """The ruling brief carries the rule and the reviews enforce it."""

    def test_the_ruling_brief_carries_the_rule_and_no_other_does(self) -> None:
        """Only the RULING brief has the ticket sentence."""
        pinned(brief.Kind.RULING, [ORDER_TICKET])
        for kind in (*REVIEWS, *OTHERS):
            has_none(text(kind), [ORDER_TICKET])

    def test_the_plan_and_execution_reviews_carry_the_review_sentence(self) -> None:
        """REVIEW_FULL, REVIEW_PLAN and REVIEW_EXECUTION carry it; no other does."""
        for kind in REVIEWS:
            pinned(kind, [ORDER_REVIEW])
        for kind in (brief.Kind.RULING, *OTHERS):
            has_none(text(kind), [ORDER_REVIEW])

    def test_the_reference_holds_the_rule_the_briefs_carry(self) -> None:
        """rules.md and adversarial-review.md hold the rule."""
        for name in ("rules.md", "adversarial-review.md"):
            assert_that(words(read(name)), contains_string("a table of the full order"))

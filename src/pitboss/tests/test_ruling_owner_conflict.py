"""A Done-when in conflict with an owner decision is escalated (pitboss#283)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_item

from .. import brief, briefruling
from .briefmake import pinned, text
from .test_evidence_rules import read, words

SENTENCE = (
    "a Done-when that cannot be met without reversing a decision of the owner"
    " (a closed owner ticket, a rule, a recorded ruling) is `Ruling: escalate to"
    " the owner`, at once, with the artifact (what happened, the recommendation,"
    " the mitigation), and never `reshape`, `split` or `abandon` around the"
    " conflict."
)


class TestOwnerConflict(unittest.TestCase):
    """Done-when: rules.md, the ruling brief and this test."""

    def test_rules_md_states_the_rule(self) -> None:
        """rules.md holds the sentence in the ruling section."""
        assert_that(words(read("rules.md")), contains_string(SENTENCE))

    def test_the_ruling_brief_carries_the_sentence(self) -> None:
        """The brief the sweep prints has the sentence as a line of its own."""
        pinned(brief.Kind.RULING, [f"Owner decisions: {SENTENCE}"])
        found = text(brief.Kind.RULING).splitlines()
        assert_that(found, has_item(briefruling.OWNER_CONFLICT))

    def test_the_rule_is_in_no_other_brief(self) -> None:
        """Only the ruling brief carries it."""
        for kind in brief.Kind:
            if kind is not brief.Kind.RULING:
                assert_that(SENTENCE in words(text(kind)), equal_to(False), kind.name)

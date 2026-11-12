"""I27 and the other cases about what a hand-back checks (pitboss#444).

Case 27: a body whose Evidence blocks were expanded at another commit than its
last ``Head:`` line is refused by the hand-back check.
"""

import unittest

from .. import handbackcheck
from .cleanworld import same
from .test_evidence_head import HEAD, OTHER, SECTION, block_of
from .test_hand_back_done import _pulled
from .test_register_rules import shown


def _body(recorded: str) -> str:
    return f"Fixes #7\n\n{SECTION}{block_of(recorded)}\nHead: {HEAD}\n"


class TestStaleEvidence(unittest.TestCase):
    """I27: Evidence from another tree is refused at the hand-back."""

    def test_i27_a_block_expanded_at_another_head_is_refused(self) -> None:
        """The block of the commit before is named; the head's block passes."""
        stale = _pulled(HEAD, _body(OTHER), [])
        fresh = _pulled(HEAD, _body(HEAD), [])
        said = [
            each
            for each in handbackcheck.pull_lines(stale)
            if "re-run `uvx pitboss expand`" in each
        ]
        again = [
            each
            for each in handbackcheck.pull_lines(fresh)
            if "re-run `uvx pitboss expand`" in each
        ]
        same((len(said), again), (1, []))

    def test_i27_plan_check_refuses_a_block_from_another_head(self) -> None:
        """Holds on main too (evidence-head): the head's block passes, another fails."""
        ran = shown(
            "test_evidence_head",
            "test_a_block_from_the_commit_before_the_head_is_refused",
        )
        same(ran, 1)

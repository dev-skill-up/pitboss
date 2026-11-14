"""The Plan review briefs require the output of ``plan-check`` (pitboss#192)."""

import unittest

from .. import brief
from .briefmake import pinned

PLAN_CHECK_BRIEF = (
    "Plan check: before you approve a Plan, the PR needs a"
    " comment whose first line is `Plan check` and whose last line is `Plan check:"
    " ok`, the output of `uvx pitboss plan-check <body file>` for this Plan (its"
    " `Plan digest:` line is the one you record); without it, or with a row that"
    " it says was NOT RUN (a command that cannot start, that waits on a lock or a"
    " queue, or that exceeds `timeout 598`), the Plan is changes needed and you do"
    " not approve it (keyword: plan-check, pitboss#192)."
)


class TestPlanCheckBrief(unittest.TestCase):
    """The Plan review briefs carry the rule."""

    def test_the_plan_reviews_require_the_check(self) -> None:
        """Done-when: the full review and the Plan review say it."""
        pinned(brief.Kind.REVIEW_FULL, [PLAN_CHECK_BRIEF])
        pinned(brief.Kind.REVIEW_PLAN, [PLAN_CHECK_BRIEF])

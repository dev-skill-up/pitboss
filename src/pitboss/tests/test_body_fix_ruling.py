"""A body fix between two rejections of one head (pitboss#146, keyword: ruling)."""

import unittest

from hamcrest import assert_that, contains_string

from . import says
from .test_commands import sweep
from .test_slot_commands import next_output
from . import test_flow_sweep as flow


class TestBodyFix(unittest.TestCase):
    """The history of pitboss#146: a body fix between two rejections of one head."""

    def test_ruling_due_after_a_body_fix_between_two_rejections_at_one_head(
        self,
    ) -> None:
        """The #146 history: two reviews of one head, the body edited between."""
        now = "Fixes #1\n\n## Plan\nthe plan\n\n## Execution\nthe fixed work\n"
        before = "Fixes #1\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"
        rounds = [
            flow.reading(flow.graded(flow.APPROVED, flow.CHANGES, 1), before),
            flow.reading(flow.graded(flow.APPROVED, flow.CHANGES, 2), now),
        ]
        here = flow.world_with(rounds, body=now)
        says.says(sweep(here).out, flow.RULING_LINE)
        assert_that(
            "".join(flow.listed_for_third(here)), contains_string(flow.RULING_LINE)
        )
        assert_that(
            next_output(here),
            contains_string("make an Opus ruling: owner/project#3: Opus agent"),
        )

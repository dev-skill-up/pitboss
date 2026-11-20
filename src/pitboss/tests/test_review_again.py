"""A reviewed head is offered the fix, never a second review (pitboss#165)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import shapes
from . import decisionline, test_flow_sweep, test_plan_revision, world

THIRD = "repos/owner/project/pulls/3"
NEEDED = "changes needed"
REVISE = "WORKER: owner/project#3: revise the PLAN only"
CASES = [
    # (the review's Plan grade, its Execution grade), the kind listed
    ((NEEDED, NEEDED), REVISE),  # a combined review
    ((NEEDED, None), REVISE),  # a review of the Plan alone
    (("approved", NEEDED), ""),  # the Execution is ruled on first (pitboss#390)
]


def listed_for(posted: shapes.Comment, draft: bool) -> str:
    """PR 3's decision in ``slots next`` with the one review posted.

    Args:
        posted: the review comment.
        draft: whether PR 3 is a draft.

    Returns:
        The line.
    """
    here = test_flow_sweep.with_complete_run(test_plan_revision.world_with(posted))
    third = here.bodies[THIRD]
    here.bodies[THIRD] = {**third, "draft": draft}  # type: ignore[dict-item]
    out = world.invoke(here, "slots", "next", here.config, *test_plan_revision.AFTER)
    return decisionline.of(out.out, "owner/project#3")


class TestReviewedHead(unittest.TestCase):
    """The newest review of the current head is changes needed."""

    def test_the_fix_is_listed_and_no_review_of_the_same_head(self) -> None:
        """A draft and a ready PR, a combined review and a Plan-alone review."""
        for draft in (True, False):
            for (plan, execution), kind in CASES:
                posted = test_plan_revision.review_comment(NEEDED, plan, execution)
                line = listed_for(posted, draft)
                # a review of the head that asks for changes is fixed, a draft
                # whose Plan is approved included (pitboss#176)
                fixed = kind in line
                assert_that(
                    (draft, plan, execution, fixed),
                    equal_to((draft, plan, execution, True)),
                )
                assert_that((bool(line), "REVIEWER" in line), equal_to((True, False)))

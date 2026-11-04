"""A reviewed head is offered the fix, never a second review (pitboss#165)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import shapes
from . import test_plan_revision, world

THIRD = "repos/owner/project/pulls/3"
NEEDED = "changes needed"
CASES = [
    # (the review's Plan grade, its Execution grade), the kind listed
    ((NEEDED, NEEDED), "(revise the plan,"),  # a combined review
    ((NEEDED, None), "(revise the plan,"),  # a review of the Plan alone
    (("approved", NEEDED), "(fix the review,"),
]


def listed_for(posted: shapes.Comment, draft: bool) -> str:
    """PR 3's line of ``slots next`` with the one review posted.

    Args:
        posted: the review comment.
        draft: whether PR 3 is a draft.

    Returns:
        The line.
    """
    here = test_plan_revision.world_with(posted)
    third = here.bodies[THIRD]
    here.bodies[THIRD] = {**third, "draft": draft}  # type: ignore[dict-item]
    out = world.invoke(here, "slots", "next", here.config, *test_plan_revision.AFTER)
    return "".join(each for each in out.out.splitlines() if "project#3 (" in each)


class TestReviewedHead(unittest.TestCase):
    """The newest review of the current head is changes needed."""

    def test_the_fix_is_listed_and_no_review_of_the_same_head(self) -> None:
        """A draft and a ready PR, a combined review and a Plan-alone review."""
        for draft in (True, False):
            for (plan, execution), kind in CASES:
                posted = test_plan_revision.review_comment(NEEDED, plan, execution)
                line = listed_for(posted, draft)
                # a draft whose Plan is approved is undrafted first (pitboss#156)
                fixed = kind in line or (draft and plan == "approved" and not line)
                assert_that(
                    (draft, plan, execution, fixed),
                    equal_to((draft, plan, execution, True)),
                )
                assert_that("review it" in line, equal_to(False))

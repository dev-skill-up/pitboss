"""A revised Plan is offered a Plan-only review before any ticket (pitboss#167)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, less_than

from .. import shapes
from . import fakes, test_flow_sweep, test_slot_commands
from .test_commands import sweep
from .says import says

HEAD = test_flow_sweep.HEAD
OLDER = test_flow_sweep.OLDER
REVISED = fakes.PLAN_AND_EXECUTION + "\nThe Plan was rewritten after the review.\n"
REVIEW_KIND = "(review it (a reviewer that is not its author)"
PLAN_ALONE = "SUGGESTION 2 of 3: review the Plan alone: owner/project#3"


def rejection(sha: str, read: str | None) -> shapes.Comment:
    """A review of PR 3 that grades the Plan changes needed.

    Args:
        sha: the head it reviewed.
        read: the body it read, or None for a review that records none.

    Returns:
        The comment.
    """
    review = test_flow_sweep.graded(test_flow_sweep.CHANGES, None, 1, sha)
    return review if read is None else test_flow_sweep.reading(review, read)


def listing(sha: str, read: str | None, body: str, standing: str) -> str:
    """What ``slots next`` prints for PR 3, checked against the sweep's word.

    Args:
        sha: the head the one review named.
        read: the body that review read, or None when it records none.
        body: PR 3's body now.
        standing: the ``review=`` word the sweep must print for PR 3.

    Returns:
        The output of ``slots next``.
    """
    here = test_flow_sweep.world_with(
        [rejection(sha, read)], body=body, head={"sha": HEAD, "ref": "branch-3"}
    )
    swept = [x for x in sweep(here).out.splitlines() if "project#3 " in x]
    says("".join(swept), f"review={standing}")
    return test_slot_commands.next_output(here)


class TestRevisedPlan(unittest.TestCase):
    """The two states of the ticket, and the control that is a fix."""

    def test_the_plan_was_rewritten_on_a_new_head(self) -> None:
        """review=older-head, CI green: a review of the Plan alone, before tickets."""
        out = listing(OLDER, None, REVISED, "older-head")
        assert_that(out, contains_string(REVIEW_KIND))
        assert_that(out, contains_string(PLAN_ALONE))
        assert_that(out.index("project#3 ("), less_than(out.index("project#9 (")))

    def test_the_plan_was_edited_on_the_live_body(self) -> None:
        """The head is the reviewed one, the body is not: the same review line."""
        read = fakes.PLAN_AND_EXECUTION
        out = listing(HEAD, read, REVISED, "older-body")
        assert_that(out, contains_string(REVIEW_KIND))
        assert_that(out, contains_string(PLAN_ALONE))

    def test_the_plan_was_not_edited(self) -> None:
        """The same body and head: the fix line, the revision of the Plan."""
        read = fakes.PLAN_AND_EXECUTION
        out = listing(HEAD, read, read, "plan-changes-needed")
        assert_that(out, contains_string("(revise the plan,"))

    def test_t221_the_unmoved_head_is_offered_for_the_plan_review_again(
        self,
    ) -> None:
        """The head did not move, the body did: the Plan alone is reviewed again."""
        out = listing(
            HEAD,
            fakes.PLAN_AND_EXECUTION,
            REVISED,
            "older-body",
        )
        assert_that(out, contains_string(PLAN_ALONE))
        assert_that("empty commit" in out, equal_to(False))

"""The rounds and rulings that decide escalation are kept per stage (pitboss#222)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import bodydigest, expansion, flowquestions, flowstate, stagerounds, steps
from .test_flow import (
    EXECUTION_REJECTED,
    OLDER,
    PLAN_REJECTED,
    expect,
    graded,
    ruling,
    state,
)
from .linting import block

PLAN_FIRST = graded(*PLAN_REJECTED, 1, sha=OLDER)
PLAN_SECOND = graded(*PLAN_REJECTED, 2, sha=OLDER)
RULED = ruling(3)


def ruled(pr: flowstate.PullState) -> bool:
    """Whether the newest ruling of a PR is the Plan stage's.

    Args:
        pr: the PR.

    Returns:
        What ``stagerounds.plan_stage_ruled`` says of its ruling and reviews.
    """
    return stagerounds.plan_stage_ruled(
        flowstate.newest_ruling(pr), flowquestions.regular_reviews(pr)
    )


class TestPerStage(unittest.TestCase):
    """dev-skill-up/pitboss#217: two Plan rejections, a ruling, approval in round 3."""

    def test_t222_the_first_execution_rejection_is_fixed_not_escalated(self) -> None:
        """The Plan stage's ruling leaves the Execution its fix round."""
        first = graded(*EXECUTION_REJECTED, 4)
        pr = state(PLAN_FIRST, PLAN_SECOND, first, comments=[RULED])
        expect(steps.worker(steps.Task.FIX_EXECUTION), pr)

    def test_t222_the_second_execution_rejection_prints_the_ruling(self) -> None:
        """A fix, then a ruling on a second rejection."""
        reviews = (
            PLAN_FIRST,
            PLAN_SECOND,
            graded(*EXECUTION_REJECTED, 4, sha=OLDER),
            graded(None, EXECUTION_REJECTED[1], 5),
        )
        expect(steps.opus_ruling(), state(*reviews, comments=[RULED]))

    def test_t222_a_rejection_after_an_execution_stage_ruling_is_the_owners(
        self,
    ) -> None:
        """The ruling written after the approval is the Execution's."""
        reviews = (
            PLAN_FIRST,
            PLAN_SECOND,
            graded(*EXECUTION_REJECTED, 4, sha=OLDER),
            graded(None, EXECUTION_REJECTED[1], 5, sha=OLDER),
            graded(None, EXECUTION_REJECTED[1], 7),
        )
        pr = state(*reviews, comments=[RULED, ruling(6)])
        expect(steps.pause_for_owner(), pr)

    def test_t222_the_ruling_is_the_plan_stages_until_the_plan_is_approved(
        self,
    ) -> None:
        """The stage is read from the order of the approval and the ruling."""
        planned = state(PLAN_FIRST, PLAN_SECOND, comments=[RULED])
        assert_that(ruled(planned), equal_to(True))
        later = state(graded(*EXECUTION_REJECTED, 1), comments=[ruling(2)])
        assert_that(ruled(later), equal_to(False))
        assert_that(ruled(state(PLAN_FIRST)), equal_to(False))


class TestOneDigest(unittest.TestCase):
    """The Plan digest has one definition (pitboss#399)."""

    def test_t399_only_the_collapsed_digest_is_compared(self) -> None:
        """The legacy readers are gone; a section has one digest, ``section_digest``."""
        for module in (bodydigest, expansion):
            for gone in ("legacy_of_section", "accepted"):
                assert_that(hasattr(module, gone), equal_to(False))
        digest = expansion.section_digest("## Plan\nx\n")
        assert_that(digest, equal_to(expansion.section_digest("## Plan\nx\n")))
        assert_that(digest != expansion.section_digest("## Plan\ny\n"), equal_to(True))

    def test_t399_the_digest_before_the_collapse_is_not_accepted(self) -> None:
        """The section as it is stood in for the collapsed one until this ticket."""
        made = block("true", "x\n")
        section = f"## Plan\n{made}"
        accepted = expansion.accepted_digests(section)
        assert_that(expansion.text_digest(section) in accepted, equal_to(False))

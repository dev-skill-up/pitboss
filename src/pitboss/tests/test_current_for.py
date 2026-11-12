"""An approval is read as current only for the subject it was about.

The keyword is current-for.

bats-lang/quire#1120: a Plan approved at one digest stayed approved after the Plan
was revised. One test for each pair of a stored verdict and the digest or head it
was recorded against.
"""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to, is_

from .. import current, expansion, flow, flowstate, plandigest, shapes, steps
from . import fakes, test_flow
from .test_flow import APPROVED, CHANGES, Task

REVISED = test_flow.BODY.replace("the plan", "a better plan")
Subject = current.Subject


def plan_digest(body: str) -> str:
    """The Plan digest a review records for a body.

    Args:
        body: the PR body.

    Returns:
        The digest of its Plan section.
    """
    return expansion.accepted_digests(plandigest.section(body))[0]


def approving(second: int, body: str, sha: str = fakes.HEAD) -> shapes.Graded:
    """A review that approves the Plan and rejects the Execution, with its digest.

    Args:
        second: when it was written.
        body: the body whose Plan it read.
        sha: the head it reviewed.

    Returns:
        The review.
    """
    review = test_flow.graded(APPROVED, CHANGES, second, sha=sha)
    return dataclasses.replace(review, plan_digest=plan_digest(body))


class TestCurrentFor(unittest.TestCase):
    """The function, for each subject."""

    def test_c31_plan_digest_pair(self) -> None:
        """A Plan digest is current for the Plan it read only."""
        digest = plan_digest(test_flow.BODY)
        section = plandigest.section(test_flow.BODY)
        assert_that(current.current_for(Subject.PLAN, digest, section), is_(True))
        other = plandigest.section(REVISED)
        assert_that(current.current_for(Subject.PLAN, digest, other), is_(False))

    def test_c31_head_pair(self) -> None:
        """A reviewed SHA is current for the head it names, never an older one."""
        head = fakes.HEAD
        assert_that(current.current_for(Subject.HEAD, head[:7], head), is_(True))
        assert_that(current.current_for(Subject.HEAD, fakes.OLDER, head), is_(False))
        assert_that(current.current_for(Subject.HEAD, "", head), is_(False))

    def test_c31_body_pair(self) -> None:
        """A body digest is current for the body it read only."""
        assert_that(current.current_for(Subject.BODY, "a", "a"), is_(True))
        assert_that(current.current_for(Subject.BODY, "a", "b"), is_(False))


class TestPairs(unittest.TestCase):
    """Each stored approval, in the flow."""

    def test_c31_the_plan_approval_does_not_outlive_the_plan(self) -> None:
        """A Plan revised after its approval is not approved."""
        review = approving(1, test_flow.BODY)
        same = test_flow.state(review)
        revised = test_flow.state(review, body=REVISED)
        assert_that(flow.plan_approved(same), is_(True))
        assert_that(flow.plan_approved(revised), is_(False))
        assert_that(flow.plan_revised(revised), is_(True))

    def test_c31_a_revised_plan_after_a_ruling_is_reviewed_again_body_only(
        self,
    ) -> None:
        """Ruled, revised in the body, nothing pushed: the Plan is reviewed alone."""
        ruled = test_flow.ruling(2, line="Ruling: revise the plan")
        pr = test_flow.state(
            approving(1, test_flow.BODY), comments=[ruled], body=REVISED
        )
        want = flow.plancheckflow.review(pr, steps.Stage.PLAN_ONLY)
        assert_that(want.step, equal_to(steps.Step.REGULAR_REVIEW))
        test_flow.expect(want, pr)

    def test_c31_a_revised_plan_after_a_ruling_is_reviewed_again_after_a_push(
        self,
    ) -> None:
        """Ruled, revised, head moved: no fix of the review, the Plan is reviewed."""
        ruled = test_flow.ruling(2, line="Ruling: revise the plan")
        old = approving(1, test_flow.BODY, sha=fakes.OLDER)
        pr = test_flow.state(old, comments=[ruled], body=REVISED)
        step = flow.next_step(pr)
        assert_that(step == steps.worker(Task.FIX_EXECUTION), is_(False))
        assert_that(step.step, equal_to(steps.Step.REGULAR_REVIEW))
        assert_that(step.stage, equal_to(steps.Stage.PLAN_ONLY))

    def test_c31_the_execution_approval_does_not_outlive_the_head(self) -> None:
        """A review of an older head is not the review of this head."""
        old = test_flow.graded(APPROVED, APPROVED, 1, sha=fakes.OLDER)
        assert_that(flow.newest_counting_review(test_flow.state(old)), equal_to(None))

    def test_c31_the_review_does_not_outlive_the_body(self) -> None:
        """A review that read another body does not count."""
        read = test_flow.reading(test_flow.graded(APPROVED, APPROVED, 1), "other body")
        assert_that(flow.newest_counting_review(test_flow.state(read)), equal_to(None))

    def test_c31_the_plan_check_does_not_outlive_the_plan(self) -> None:
        """A clean ``plan-check`` of one Plan is none for a revised one."""
        pr = test_flow.state(body=REVISED)
        newest = flow.plancheckflow.newest_check(
            pr.pull.body, [test_flow.clean_check(test_flow.BODY)], pr.trusted
        )
        assert_that(newest, equal_to(None))

    def test_c31_the_ruling_does_not_apply_twice(self) -> None:
        """A revise-the-plan ruling is applied once the Plan differs."""
        ruled = test_flow.ruling(2, line="Ruling: revise the plan")
        unrevised = test_flow.state(approving(1, test_flow.BODY), comments=[ruled])
        assert_that(flow.plan_revised(unrevised), is_(False))
        assert_that(flowstate.plan_edited_without_ruling(unrevised), is_(False))

"""The Plan digest ignores the ids of a CI pointer's run and job (pitboss#475).

See keywords plan-digest-urls and plan-digest-rulings.
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to, is_not

from .. import flow, flowstate, shapes, steps
from . import test_flow
from .test_flow import state
from .test_plan_digest_collapse import digest

PLAN = test_flow.BODY
EDITED_PLAN = PLAN.replace("the plan", "the plan, edited")
REVISE = "Ruling: revise the plan"
POINTED = (
    "## Plan\n1. Run `make {word}`.\n\n2. CI: workflow `check.yml`, job `check`,"
    " greppable `test_name`; run https://github.com/o/r/actions/runs/{run}/job/{job}"
    "\n\n## Execution\nthe work\n"
)


def pointed(run: int, job: int, word: str = "all") -> str:
    """A body whose Plan has a CI pointer that names a run and a job.

    Args:
        run: the run's id.
        job: the job's id.
        word: the last word of the first row.

    Returns:
        The body.
    """
    text = POINTED.replace("{run}", str(run)).replace("{job}", str(job))
    return text.replace("{word}", word)


def read(body: str, second: int = 1, sha: str = test_flow.HEAD) -> shapes.Graded:
    """An approving review of the Plan that records the digest of a body's Plan.

    Args:
        body: the body it read.
        second: the second of the minute it was written.
        sha: the head it reviewed.

    Returns:
        The review.
    """
    review = test_flow.graded(*test_flow.EXECUTION_REJECTED, second, sha=sha)
    return dataclasses.replace(review, plan_digest=digest(body))


def edited(
    first: str, now: str, rulings: Sequence[shapes.Comment] = (), second: int = 1
) -> flow.PullState:
    """A PR whose review read one Plan and whose body now has another.

    Args:
        first: the body the review read.
        now: the body now.
        rulings: its Opus rulings.
        second: the second of the minute the review was written.

    Returns:
        The state.
    """
    return state(read(first, second), comments=rulings, body=now)


def revised_then_steps(second: int) -> Sequence[shapes.Comment]:
    """A ruling `revise the plan` at the second second, then `do these steps`.

    Args:
        second: the second of the minute the later ruling was written.

    Returns:
        The two rulings.
    """
    return [test_flow.ruling(2, line=REVISE), test_flow.ruling(second)]


class TestTheRunUrlsAreNotThePlan(unittest.TestCase):
    """Done-when 3: the ids of a CI pointer's run and job are not an edit."""

    def test_only_the_urls_rewritten_is_no_edit_and_a_word_or_repository_is(
        self,
    ) -> None:
        """The nearest inputs: a changed word, or another repository."""
        other = pointed(1, 2).replace("o/r", "o/s")
        cases = {
            "urls": (pointed(77, 88), False),
            "word": (pointed(77, 88, "test"), True),
            "repository": (other, True),
        }
        for name, (now, changed) in cases.items():
            with self.subTest(name):
                pr = edited(pointed(1, 2), now)
                found = flowstate.plan_edited_without_ruling(pr)
                assert_that(found, equal_to(changed))


class TestARulingAfterTheApprovalDoesNotCancelTheRevision(unittest.TestCase):
    """Done-when 1: `revise the plan` then `do these steps`."""

    def test_the_two_rulings_in_that_order_leave_no_plan_edited(self) -> None:
        """The step is not PLAN EDITED."""
        pr = edited(PLAN, EDITED_PLAN, revised_then_steps(3))
        assert_that(flow.next_step(pr).step, is_not(steps.Step.PLAN_EDITED))

    def test_without_the_revision_or_with_it_before_the_review_it_is_edited(
        self,
    ) -> None:
        """The nearest inputs: no revision, and a revision older than the review."""
        cases = {
            "no revision": ([test_flow.ruling(3)], 1),
            "revision first": (revised_then_steps(4), 3),
        }
        for name, (rulings, second) in cases.items():
            with self.subTest(name):
                pr = edited(PLAN, EDITED_PLAN, rulings, second)
                assert_that(flowstate.plan_edited_without_ruling(pr), equal_to(True))

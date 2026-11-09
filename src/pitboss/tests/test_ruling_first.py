"""A rejected Execution is ruled on first, and no code answers it by a Plan round.

The Execution stage starts with an Opus ruling; the fix round follows a recorded
ruling (keywords: ruling-first, unfixed-execution, pitboss#390). A Plan revised
and approved after an Execution rejection leaves the head moved by an empty
commit only, and the rejected Execution still stands.
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import flow, shapes, steps
from . import test_flow, test_flow_sweep as scenes
from .suggestions import kind_of_third
from .test_commands import sweep
from .test_flow import APPROVED, CHANGES, OLDER, expect, graded, state
from .test_flow_sweep import RULING_LINE
from .test_slot_commands import next_output

RULING_URL = "https://example.org/ruling/2"
PLAN_ALONE = graded(APPROVED, None, 3)
REJECTED = graded(APPROVED, CHANGES, 1, sha=OLDER)


def unmoved(pr: flow.PullState) -> flow.PullState:
    """A PR whose head differs from every reviewed head by an empty commit.

    Args:
        pr: the PR.

    Returns:
        The PR with that recorded.
    """
    return dataclasses.replace(pr, unchanged_since=lambda sha: True)


def ruled(word: str, second: int = 2) -> Sequence[shapes.Comment]:
    """The comments of a ruling.

    Args:
        word: what it rules.
        second: the second of the minute it was written.

    Returns:
        The comments.
    """
    return [test_flow.ruling(second, line=f"Ruling: {word}")]


class TestRulingFirst(unittest.TestCase):
    """The first step after an Execution rejection."""

    def test_a_rejected_execution_gets_the_ruling_and_a_rejected_plan_the_round(
        self,
    ) -> None:
        """Both at one head: the Plan is revised, the Execution is ruled on."""
        expect(steps.worker(steps.Task.REVISE_PLAN), state(graded(CHANGES, None, 1)))
        expect(steps.opus_ruling(), state(graded(APPROVED, CHANGES, 1)))

    def test_the_fix_round_follows_a_recorded_ruling(self) -> None:
        """Only once the ruling is recorded: the ruling's own step."""
        pr = state(REJECTED, comments=ruled("do these steps"))
        expect(steps.worker(steps.Task.RULING_STEPS), pr)

    def test_a_rejection_after_the_ruling_pauses(self) -> None:
        """The ruling was used and the Execution is still rejected."""
        pr = state(REJECTED, graded(None, CHANGES, 3), comments=ruled("split"))
        expect(steps.pause_for_owner(), pr)


class TestUnfixedExecution(unittest.TestCase):
    """The Plan approved alone at a head only an empty commit moved."""

    def test_a_ruled_revision_is_followed_by_the_fix_of_the_execution(self) -> None:
        """The offer is the fix of the review, with the ruling named."""
        pr = unmoved(state(REJECTED, PLAN_ALONE, comments=ruled("revise the plan")))
        expect(steps.worker(steps.Task.FIX_EXECUTION, RULING_URL), pr)

    def test_the_ruling_decides_when_it_is_not_a_revision(self) -> None:
        """A ruling of another word gives its first step; none, the ruling is due."""
        ruling = ruled("do these steps")
        expect(
            steps.worker(steps.Task.RULING_STEPS),
            unmoved(state(REJECTED, PLAN_ALONE, comments=ruling)),
        )
        expect(steps.opus_ruling(), unmoved(state(REJECTED, PLAN_ALONE)))

    def test_a_ruling_before_the_rejection_was_used(self) -> None:
        """The owner decides."""
        rejected = graded(APPROVED, CHANGES, 3, sha=OLDER)
        pr = unmoved(state(rejected, PLAN_ALONE, comments=ruled("split", 1)))
        expect(steps.pause_for_owner(), pr)

    def test_the_execution_is_reviewed_when_nothing_stands_rejected(self) -> None:
        """Code moved, the newest Execution verdict is approved, or none was graded."""
        approved = graded(APPROVED, APPROVED, 2, sha=OLDER)
        pushed = state(REJECTED, PLAN_ALONE, comments=ruled("revise the plan"))
        review = steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN)
        expect(review, pushed)
        expect(review, unmoved(state(REJECTED, approved, PLAN_ALONE)))
        expect(review, unmoved(state(PLAN_ALONE)))

    def test_a_plan_approved_at_an_older_head_is_ruled_on_too(self) -> None:
        """No review of the head: the same answer, from the CI gate."""
        approved = graded(APPROVED, None, 1, sha=OLDER)
        pr = state(approved, graded(None, CHANGES, 2, sha=OLDER))
        expect(steps.regular_review(steps.Stage.EXECUTION_ONLY), pr)
        expect(steps.opus_ruling(), unmoved(pr))


class TestWorld(unittest.TestCase):
    """The sweep and ``slots next`` on the comments of that history."""

    def test_the_fix_round_is_listed_and_no_review(self) -> None:
        """The incident of pitboss#386: not `review the Execution`."""
        here = scenes.unfixed_after_the_ruling()
        assert_that(sweep(here).out.count("RULING DUE"), equal_to(0))
        assert_that(kind_of_third(here), equal_to("fix the review"))

    def test_the_ruling_is_due_when_none_is_recorded(self) -> None:
        """A rejected Execution and a Plan revised with no ruling."""
        rejected = scenes.graded(scenes.APPROVED, scenes.CHANGES, 1, sha=scenes.OLDER)
        here = scenes.unfixed_rounds(rejected, scenes.graded(scenes.APPROVED, None, 3))
        assert_that(sweep(here).out, contains_string(RULING_LINE))
        assert_that(next_output(here).count("project#3 ("), equal_to(0))

    def test_a_pushed_fix_is_reviewed_and_a_derived_file_is_no_code(self) -> None:
        """The head carries code the rejection has not seen, or only a rebuilt zip."""
        for files, kind in (
            (["a.py"], "review the Execution"),
            (["skill-zips/sweep.zip"], "fix the review"),
        ):
            with self.subTest(files):
                here = scenes.unfixed_after_the_ruling(files)
                assert_that(kind_of_third(here), equal_to(kind))

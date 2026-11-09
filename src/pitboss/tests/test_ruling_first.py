"""A rejected Execution is ruled on first, and no code answers it by a Plan round.

Keywords: ruling-first, unfixed-execution (pitboss#390). The Execution stage
starts with an Opus ruling; the fix round follows a recorded ruling. A Plan
revised and approved after an Execution rejection leaves the head moved by an
empty commit only, and the rejected Execution still stands.
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import flow, shapes, steps
from . import test_flow, unfixed, world
from .suggestions import kind_of_third, next_output
from .test_commands import sweep
from .test_flow import APPROVED, CHANGES, OLDER, expect, graded, state
from .test_flow_sweep import RULING_LINE

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
        expect(steps.fix_execution(RULING_URL), pr)

    def test_the_ruling_of_another_word_gives_its_own_step(self) -> None:
        """A ruling that is not a Plan revision gives its first step."""
        pr = unmoved(state(REJECTED, PLAN_ALONE, comments=ruled("do these steps")))
        expect(steps.worker(steps.Task.RULING_STEPS), pr)

    def test_with_no_ruling_the_ruling_is_due(self) -> None:
        """A rejected Execution is never fixed before a ruling."""
        expect(steps.opus_ruling(), unmoved(state(REJECTED, PLAN_ALONE)))

    def test_a_ruling_before_the_rejection_was_used(self) -> None:
        """The owner decides."""
        rejected = graded(APPROVED, CHANGES, 3, sha=OLDER)
        pr = unmoved(state(rejected, PLAN_ALONE, comments=ruled("split", 1)))
        expect(steps.pause_for_owner(), pr)

    def test_a_head_that_code_moved_is_reviewed(self) -> None:
        """The nearest input: the fix was pushed, so the Execution is reviewed."""
        pr = state(REJECTED, PLAN_ALONE, comments=ruled("revise the plan"))
        expect(steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN), pr)

    def test_an_approved_execution_is_reviewed(self) -> None:
        """The newest Execution verdict is approved: nothing stands rejected."""
        approved = graded(APPROVED, APPROVED, 2, sha=OLDER)
        pr = unmoved(state(REJECTED, approved, PLAN_ALONE))
        expect(steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN), pr)

    def test_a_plan_never_graded_for_the_execution_is_reviewed(self) -> None:
        """No review graded the Execution at all."""
        pr = unmoved(state(PLAN_ALONE))
        expect(steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN), pr)

    def test_a_plan_approved_at_an_older_head_is_ruled_on_too(self) -> None:
        """No review of the head: the same answer, from the CI gate."""
        approved = graded(APPROVED, None, 1, sha=OLDER)
        rejected = graded(None, CHANGES, 2, sha=OLDER)
        pr = state(approved, rejected)
        expect(steps.regular_review(steps.Stage.EXECUTION_ONLY), pr)
        expect(steps.opus_ruling(), unmoved(pr))


class TestWorld(unittest.TestCase):
    """The sweep and ``slots next`` on the comments of that history."""

    def test_the_fix_round_is_listed_and_no_review(self) -> None:
        """The incident of pitboss#386: not `review the Execution`."""
        here = unfixed.after_the_ruling()
        assert_that(kind_of_third(here), equal_to("fix the review"))
        assert_that("RULING DUE" in sweep(here).out, equal_to(False))

    def test_the_ruling_is_due_when_none_is_recorded(self) -> None:
        """A rejected Execution and a Plan revised with no ruling."""
        here = unfixed.rounds(unfixed.REJECTED, unfixed.PLAN_APPROVED)
        assert_that(sweep(here).out, contains_string(RULING_LINE))
        lines = [x for x in next_output(here).splitlines() if "project#3 (" in x]
        assert_that(lines, equal_to([]))

    def test_a_pushed_fix_is_reviewed(self) -> None:
        """The head carries code the rejection has not seen."""
        here = unfixed.after_the_ruling()
        here.bodies[f"{world.PROJECT}/commits/2"] = {"files": [{"filename": "a.py"}]}
        assert_that(kind_of_third(here), equal_to("review the Execution"))

    def test_a_derived_file_alone_moved_nothing(self) -> None:
        """A rebuilt zip is no code (keyword: derived-only)."""
        here = unfixed.after_the_ruling()
        zipped = {"files": [{"filename": "skill-zips/sweep.zip"}]}
        here.bodies[f"{world.PROJECT}/commits/2"] = zipped
        assert_that(kind_of_third(here), equal_to("fix the review"))

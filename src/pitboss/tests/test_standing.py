"""A review is offered only for a head and body a worker handed back (pitboss#507).

quire#1125: a review of head 9aef3c6 was printed while the worker had not handed
back, and a rejection of it was counted as a round (keyword: standing).
"""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import bodydigest, flow, flowquestions, handbacks, standing, steps
from . import pullstates, reviewsteps, test_flow
from .test_flow import CHANGES, HEAD, OLDER, expect, graded, state

BODY_DIGEST = bodydigest.digest(test_flow.BODY)
RULING = "https://example.org/ruling/3"
STAGE = steps.Stage.PLAN_ONLY
HAND_BACK = reviewsteps.HAND_BACK
ANYTHING = (HEAD, handbacks.ANY, handbacks.ANY)
NONE = handbacks.NO_RULING


def held(*states: tuple[str, str, str]) -> handbacks.HandedBack:
    """What a worktree recorded.

    Args:
        *states: each ``(head, body digest, ruling)``.

    Returns:
        The record of a PR a worker holds.
    """
    return handbacks.HandedBack(required=True, states=frozenset(states))


def worked(pr: flow.PullState, record: handbacks.HandedBack) -> flow.PullState:
    """A PR with a worktree record.

    Args:
        pr: the PR.
        record: what its worktree recorded.

    Returns:
        The same with that recorded.
    """
    return pullstates.with_recorded(pr, handed=record)


def has_standing(
    pr: flow.PullState, stage: steps.Stage = STAGE, head: str = HEAD
) -> bool:
    """Whether the PR's head and body have a standing for a stage.

    Args:
        pr: the PR.
        stage: what the review would grade.
        head: the head the standing must be for.

    Returns:
        True when ``standing.of`` gives one for that head.
    """
    found = standing.of(pr, stage)
    return found is not None and found.head == head


class TestStanding(unittest.TestCase):
    """``standing.of`` for a head and body."""

    def test_the_record_must_name_the_head_the_body_and_the_ruling(self) -> None:
        """Each of the three is the one recorded, or there is no standing."""
        records = [
            held((HEAD, BODY_DIGEST, NONE)),
            held(ANYTHING),
            held((OLDER, BODY_DIGEST, NONE)),
            held((HEAD, "0" * 16, NONE)),
            held((HEAD, BODY_DIGEST, RULING)),
            held(),
        ]
        found = [has_standing(worked(state(), each)) for each in records]
        assert_that(found, equal_to([True, True, False, False, False, False]))

    def test_a_pr_no_worker_holds_needs_no_hand_back(self) -> None:
        """No worktree: the relock PRs and the PRs of other hands."""
        assert_that(has_standing(state()), equal_to(True))

    def test_the_newest_ruling_is_the_one_a_hand_back_must_have_seen(self) -> None:
        """A ruling is on the PR: the record names it, or the head has no standing."""
        pr = state(comments=[test_flow.ruling(3)])
        seen = has_standing(worked(pr, held((HEAD, BODY_DIGEST, RULING))))
        unseen = has_standing(worked(pr, held((HEAD, BODY_DIGEST, NONE))))
        assert_that([seen, unseen], equal_to([True, False]))

    def test_a_review_names_a_state_and_a_stage_once(self) -> None:
        """No second review of one state for a stage; another stage or state is fine."""
        review = dataclasses.replace(
            graded(test_flow.APPROVED, None, 1), body=BODY_DIGEST
        )
        other_head = dataclasses.replace(
            graded(test_flow.APPROVED, None, 1, sha=OLDER), body=""
        )
        github = test_flow.github_review(test_flow.APPROVED, 1)
        later = steps.Stage.EXECUTION_AGAINST_PLAN
        found = [
            has_standing(state(review)),
            has_standing(state(review), later),
            has_standing(state(other_head)),
            has_standing(state(github)),
        ]
        assert_that(found, equal_to([False, True, True, True]))


class TestAfterARuling(unittest.TestCase):
    """A ruling opens another review of a state a review already graded."""

    def test_a_review_before_the_ruling_does_not_name_the_state(self) -> None:
        """The steps change neither head nor body: the review follows the hand-back."""
        stage = steps.Stage.RULING_STEPS
        before = dataclasses.replace(
            graded(test_flow.APPROVED, CHANGES, 1), body=BODY_DIGEST
        )
        after = dataclasses.replace(
            graded(test_flow.APPROVED, CHANGES, 5), body=BODY_DIGEST
        )
        record = held((HEAD, BODY_DIGEST, RULING))
        ruled = [test_flow.ruling(3)]
        waiting = worked(state(before, comments=ruled), record)
        answered = worked(state(before, after, comments=ruled), record)
        found = [has_standing(waiting, stage), has_standing(answered, stage)]
        assert_that(found, equal_to([True, False]))


class TestWithoutAHandBack(unittest.TestCase):
    """What the flow prints where a review had been."""

    def test_the_review_is_the_hand_back_while_the_head_is_not_handed_back(
        self,
    ) -> None:
        """A PR with a worktree and no record is at the worker's hand-back."""
        expect(HAND_BACK, worked(state(), held()))

    def test_the_review_is_offered_once_the_head_is_handed_back(self) -> None:
        """The record names the head and the body."""
        both = steps.Stage.PLAN_AND_EXECUTION
        record = held((HEAD, BODY_DIGEST, NONE))
        expect(reviewsteps.review(both), worked(state(), record))


def rejected_after_ruling(record: handbacks.HandedBack) -> flow.PullState:
    """A PR ruled after two Plan rejections, then rejected again.

    Args:
        record: what its worktree recorded.

    Returns:
        The state.
    """
    reviews = (
        test_flow.FIRST_REJECTION,
        test_flow.SECOND_REJECTION,
        graded(*test_flow.PLAN_REJECTED, 4),
    )
    return worked(state(*reviews, comments=[test_flow.ruling(3)]), record)


class TestRounds(unittest.TestCase):
    """A rejection is a round only when a worker handed back what it graded."""

    def test_a_rejection_of_a_head_no_worker_handed_back_is_no_round(self) -> None:
        """quire#1122, #1125: the ruling's steps go to the worker again."""
        expect(
            test_flow.ruling_steps(3),
            rejected_after_ruling(held((OLDER, handbacks.ANY, handbacks.ANY))),
        )

    def test_a_rejection_of_a_handed_back_head_is_a_round(self) -> None:
        """The second rejection after the ruling pauses for the owner."""
        expect(steps.pause_for_owner(), rejected_after_ruling(held(ANYTHING)))

    def test_plan_rejections_count_distinct_handed_back_states(self) -> None:
        """quire#1120: one state graded twice is one; an unhanded one is none."""
        twice = state(
            dataclasses.replace(graded(CHANGES, None, 1), body="x"),
            dataclasses.replace(graded(CHANGES, None, 2), body="x"),
        )
        distinct = state(graded(CHANGES, None, 1, sha=OLDER), graded(CHANGES, None, 2))
        rejected = (test_flow.FIRST_REJECTION, test_flow.SECOND_REJECTION)
        unhanded = worked(state(*rejected), held(ANYTHING))
        found = [
            flowquestions.get_plan_rejections(each)
            for each in (twice, distinct, unhanded)
        ]
        assert_that(found, equal_to([1, 2, 1]))

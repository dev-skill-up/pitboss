"""Tests for the review flow of a PR (keyword: review-flow, pitboss#107).

Each row of the owner's table goes through ``next_step`` on recorded PR data
(no mocks: the data is injected), and each question alone is in
``test_flow_questions``.
"""

import dataclasses
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import flow, parsing, shapes, steps
from . import fakes

HEAD = fakes.HEAD
OLDER = fakes.OLDER
SETTINGS = fakes.settings(fakes.directory())
FORM = SETTINGS.review.form
REVIEW = dataclasses.replace(
    SETTINGS.review,
    gated=frozenset({"owner/gated"}),
    trusted=frozenset({"MEMBER"}),
    gated_form=dataclasses.replace(FORM, lines=("## Gated review", *FORM.lines[1:])),
)
BODY = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"
GREEN = shapes.CheckRun(id=1, name="build", finished=True, failed=False)
RED = shapes.CheckRun(id=2, name="test", finished=True, failed=True)
RUNNING = shapes.CheckRun(id=3, name="lint", finished=False, failed=False)
CHANGES = shapes.Verdict.CHANGES_NEEDED
APPROVED = shapes.Verdict.APPROVED
Task = steps.Task
Stage = steps.Stage
PLAN_REJECTED = (CHANGES, None)
PLAN_APPROVED_ALONE = (APPROVED, None)
EXECUTION_REJECTED = (APPROVED, CHANGES)
EVERYTHING_APPROVED = (APPROVED, APPROVED)


def graded(
    plan: shapes.Verdict | None,
    execution: shapes.Verdict | None,
    second: int,
    sha: str = HEAD,
) -> shapes.Graded:
    """A regular review as the flow reads it.

    Args:
        plan: its plan grade, None for no ``Plan:`` line.
        execution: its execution grade, None for a review of the plan alone.
        second: the second of the minute it was written.
        sha: the head it reviewed.

    Returns:
        The review.
    """
    when = f"2026-10-30T00:00:{second:02d}Z"
    return shapes.Graded(sha=sha, when=when, plan=plan, execution=execution)


FIRST_REJECTION = graded(*PLAN_REJECTED, 1, sha=OLDER)
SECOND_REJECTION = graded(*PLAN_REJECTED, 2)


def ruling(second: int, author: str = "MEMBER") -> shapes.Comment:
    """A recorded Opus ruling.

    Args:
        second: the second of the minute it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    return shapes.Comment(
        body="Opus ruling\nRuling: do these steps\n",
        author_association=author,
        created_at=f"2026-10-30T00:00:{second:02d}Z",
    )


def pull_of(**changes: object) -> shapes.Pull:
    """A PR as the API gives it, with a Plan and an Execution in its body.

    Args:
        **changes: changes to its JSON.

    Returns:
        The PR.
    """
    changes = {"body": BODY, **changes}
    return parsing.pull(json.dumps(fakes.pull_body(1, **changes)))


def state(
    *recorded: shapes.Graded,
    comments: Sequence[shapes.Comment] = (),
    checks: Sequence[shapes.CheckRun] = (GREEN,),
    **changes: object,
) -> flow.PullState:
    """The recorded data of one PR.

    Args:
        *recorded: the reviews that count.
        comments: its issue comments.
        checks: the check runs of its head.
        **changes: changes to the PR's JSON.

    Returns:
        The state.
    """
    return flow.PullState(
        pull=pull_of(**changes),
        labels=frozenset(),
        checks=checks,
        graded=recorded,
        comments=comments,
        trusted=frozenset({"MEMBER"}),
    )


def altered(pr: flow.PullState, **fields: object) -> flow.PullState:
    """A state with fields of its own changed.

    Args:
        pr: the state.
        **fields: the fields to change.

    Returns:
        The state.
    """
    return dataclasses.replace(pr, **fields)


def expect(want: steps.Next, pr: flow.PullState) -> None:
    """Check the step of a PR.

    Args:
        want: the step it must be at.
        pr: the PR.
    """
    assert_that(flow.next_step(pr), equal_to(want))


class TestTable(unittest.TestCase):
    """One test for each row of the owner's table."""

    def test_plan_rejected_the_first_time(self) -> None:
        """The worker revises the plan and changes no code."""
        expect(steps.worker(Task.REVISE_PLAN), state(graded(*PLAN_REJECTED, 1)))

    def test_plan_rejected_the_second_time(self) -> None:
        """Opus rules."""
        expect(steps.opus_ruling(), state(FIRST_REJECTION, SECOND_REJECTION))

    def test_plan_rejected_after_an_opus_ruling(self) -> None:
        """The owner decides."""
        rejected = state(
            FIRST_REJECTION, graded(*PLAN_REJECTED, 4), comments=[ruling(3)]
        )
        expect(steps.pause_for_owner(), rejected)

    def test_plan_approved_execution_not_graded(self) -> None:
        """A review of the execution against the approved plan."""
        want = steps.regular_review(Stage.EXECUTION_AGAINST_PLAN)
        expect(want, state(graded(*PLAN_APPROVED_ALONE, 1)))

    def test_execution_rejected_by_the_review_that_approves_the_plan(self) -> None:
        """The worker fixes the execution."""
        expect(steps.worker(Task.FIX_EXECUTION), state(graded(*EXECUTION_REJECTED, 1)))

    def test_execution_rejected_by_the_first_review_after_the_approval(self) -> None:
        """The worker fixes the execution."""
        reviews = state(graded(*PLAN_APPROVED_ALONE, 1), graded(None, CHANGES, 2))
        expect(steps.worker(Task.FIX_EXECUTION), reviews)

    def test_the_fixed_execution_rejected_again(self) -> None:
        """Opus rules."""
        first = graded(*EXECUTION_REJECTED, 1, sha=OLDER)
        expect(steps.opus_ruling(), state(first, graded(None, CHANGES, 2)))

    def test_execution_rejected_after_an_opus_ruling(self) -> None:
        """The owner decides."""
        first = graded(*EXECUTION_REJECTED, 1, sha=OLDER)
        rejected = state(first, graded(None, CHANGES, 3), comments=[ruling(2)])
        expect(steps.pause_for_owner(), rejected)

    def test_execution_approved_green_without_a_conflict(self) -> None:
        """Merge."""
        expect(steps.merge(), state(graded(*EVERYTHING_APPROVED, 1)))


class TestBranches(unittest.TestCase):
    """The other branches of the flow, in the order written."""

    def test_a_paused_pr_waits_for_the_owner(self) -> None:
        """Before anything else, whatever the body is."""
        labels = frozenset({steps.PAUSED_LABEL})
        expect(steps.wait_for_owner(), altered(state(body=""), labels=labels))

    def test_no_plan_and_execution_body_is_the_first_work(self) -> None:
        """The worker writes the body, before any review or gate."""
        bodiless = state(graded(*PLAN_REJECTED, 1), body="")
        expect(steps.worker(Task.FIRST_ROUND), bodiless)

    def test_a_draft_is_undrafted_when_it_can_be(self) -> None:
        """Before any CI wait or review."""
        draft = state(checks=(), draft=True)
        expect(steps.undraft(), altered(draft, undraft_clear=True))

    def test_a_draft_whose_plan_is_not_approved_gets_a_plan_review(self) -> None:
        """No CI gate on a draft; the Plan only."""
        expect(steps.regular_review(Stage.PLAN_ONLY), state(checks=(), draft=True))

    def test_a_draft_with_the_plan_approved_waits_for_the_window(self) -> None:
        """It cannot be undrafted yet."""
        approved = state(graded(*PLAN_APPROVED_ALONE, 1), checks=(), draft=True)
        expect(steps.wait_for_undraft(), approved)

    def test_nothing_runs_until_ci_finishes(self) -> None:
        """Nobody works or reviews while CI runs or has not started."""
        review = graded(*PLAN_REJECTED, 1)
        for checks in ((), (RUNNING,), (GREEN, RUNNING)):
            expect(steps.wait_for_ci(), state(review, checks=checks))

    def test_red_ci_goes_to_the_worker(self) -> None:
        """Even where a review stands."""
        expect(
            steps.worker(Task.FIX_CI), state(graded(*PLAN_REJECTED, 1), checks=(RED,))
        )

    def test_red_ci_is_never_a_rejection(self) -> None:
        """It is not counted, and it does not move a plan to Opus."""
        red = state(FIRST_REJECTION, checks=(RED,))
        found = [flow.get_plan_rejections(red), flow.next_step(red)]
        assert_that(found, equal_to([1, steps.worker(Task.FIX_CI)]))
        twice = state(FIRST_REJECTION, SECOND_REJECTION, checks=(RED,))
        expect(steps.worker(Task.FIX_CI), twice)

    def test_a_plan_approved_in_a_draft_is_carried_to_the_execution_review(
        self,
    ) -> None:
        """A review of the Execution only, the Plan carried over."""
        approved = graded(*PLAN_APPROVED_ALONE, 1, sha=OLDER)
        expect(steps.regular_review(Stage.EXECUTION_ONLY), state(approved))

    def test_no_review_is_a_review_of_both(self) -> None:
        """The first review grades the Plan and the Execution together."""
        expect(steps.regular_review(Stage.PLAN_AND_EXECUTION), state())

    def test_an_approved_execution_with_a_conflict_is_the_workers(self) -> None:
        """No new review for a conflict-only fix."""
        review = graded(*EVERYTHING_APPROVED, 1)
        conflicted = state(review, mergeable_state="dirty")
        expect(steps.worker(Task.RESOLVE_CONFLICT), conflicted)

    def test_a_review_without_a_plan_line_grades_the_execution_by_its_verdict(
        self,
    ) -> None:
        """Plan unsaid: the execution's grade is the verdict."""
        expect(steps.merge(), state(graded(None, APPROVED, 1)))

    def test_a_ruling_is_used_whatever_came_before_it(self) -> None:
        """A rejected plan after a ruling pauses, even the first one."""
        rejected = state(graded(*PLAN_REJECTED, 2), comments=[ruling(1)])
        expect(steps.pause_for_owner(), rejected)

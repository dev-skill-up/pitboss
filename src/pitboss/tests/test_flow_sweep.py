"""``pitboss sweep`` and ``slots next`` take their lines from the flow's step."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import shapes
from . import fakes, test_flow, world
from .test_commands import sweep
from .test_slot_commands import next_output

HEAD = "3" * 40
OLDER = "2" * 40
CHANGES = "changes needed"
APPROVED = "approved"
RULING_LINE = "RULING DUE owner/project#3: the review rounds hit"
PAUSE_LINE = "PAUSE owner/project#3: changes needed again after the Opus ruling"


def graded(
    plan: str | None, execution: str | None, second: int, sha: str = HEAD
) -> shapes.Comment:
    """A review comment of PR 3.

    Args:
        plan: the plan grade, or None for no ``Plan:`` line.
        execution: the execution grade, or None for no ``Execution:`` line.
        second: the second of the minute it was written.
        sha: the head it reviewed.

    Returns:
        The comment.
    """
    grades = [grade for grade in (plan, execution) if grade is not None]
    verdict = CHANGES if CHANGES in grades else APPROVED
    lines = [
        "## Review",
        f"Reviewed: {sha}",
        *([f"Plan: {plan}"] if plan else []),
        *([f"Execution: {execution}"] if execution else []),
        f"Verdict: {verdict}",
    ]
    when = f"2026-10-30T00:00:{second:02d}Z"
    return shapes.Comment(
        body="\n".join(lines) + "\n", author_association="MEMBER", created_at=when
    )


def world_with(rounds: Sequence[shapes.Comment], **changes: object) -> world.World:
    """A world whose PR 3 has the comments.

    Args:
        rounds: the comments, as the API gives them.
        **changes: changes to PR 3's JSON.

    Returns:
        The world.
    """
    here = world.make_world()
    path = fakes.page("repos/owner/project/issues/3/comments")
    here.bodies[path] = [
        {
            "body": each.body,
            "author_association": each.author_association,
            "created_at": each.created_at,
        }
        for each in rounds
    ]
    head = {"sha": HEAD, "ref": "branch-3"}
    here.bodies[f"{world.PROJECT}/pulls/3"] = fakes.pull_body(3, head=head, **changes)
    return here


def sweep_and_next(rounds: Sequence[shapes.Comment]) -> tuple[str, str]:
    """What the sweep prints, and PR 3's line of ``slots next``.

    Args:
        rounds: PR 3's comments.

    Returns:
        The sweep's output, and PR 3's line in the list (empty when none).
    """
    here = world_with(rounds)
    listed = [line for line in next_output(here).splitlines() if "project#3 (" in line]
    return sweep(here).out, "".join(listed)


TWO_PLAN_REJECTIONS = [
    graded(CHANGES, None, 1, sha=OLDER),
    graded(CHANGES, None, 2),
]
RULED = [*TWO_PLAN_REJECTIONS, test_flow.ruling(3)]
EXECUTION_TWICE = [
    graded(APPROVED, CHANGES, 1, sha=OLDER),
    graded(None, CHANGES, 2),
]


class TestSweepAndNext(unittest.TestCase):
    """RULING DUE, PAUSE, revise the plan, fix the review and review it."""

    def test_ruling_due_after_the_second_plan_rejection(self) -> None:
        """RULING DUE is printed, and PR 3 is offered for nothing."""
        swept, listed = sweep_and_next(TWO_PLAN_REJECTIONS)
        assert_that(swept, contains_string(RULING_LINE))
        assert_that("PAUSE owner" in swept, equal_to(False))
        assert_that(listed, equal_to(""))

    def test_ruling_due_after_the_fixed_execution_is_rejected_again(self) -> None:
        """The second execution rejection on the approved plan asks for a ruling."""
        swept, listed = sweep_and_next(EXECUTION_TWICE)
        assert_that(swept, contains_string(RULING_LINE))
        assert_that(listed, equal_to(""))

    def test_pause_after_the_ruling_and_another_plan_rejection(self) -> None:
        """PAUSE is printed, and PR 3 is offered for nothing."""
        swept, listed = sweep_and_next([*RULED, graded(CHANGES, None, 4)])
        assert_that(swept, contains_string(PAUSE_LINE))
        assert_that("RULING DUE" in swept, equal_to(False))
        assert_that(listed, equal_to(""))

    def test_pause_after_the_ruling_and_a_rejected_execution(self) -> None:
        """An execution rejection after the ruling pauses too."""
        rounds = [EXECUTION_TWICE[0], test_flow.ruling(2), graded(None, CHANGES, 3)]
        swept, listed = sweep_and_next(rounds)
        assert_that(swept, contains_string(PAUSE_LINE))
        assert_that(listed, equal_to(""))

    def test_a_review_that_approves_the_plan_and_asks_for_changes_is_a_round(
        self,
    ) -> None:
        """A worker round (fix the review), not RULING DUE."""
        swept, listed = sweep_and_next([graded(APPROVED, CHANGES, 1)])
        assert_that("RULING DUE" in swept or "PAUSE" in swept, equal_to(False))
        assert_that(listed, contains_string("(fix the review,"))

    def test_the_first_plan_rejection_is_a_plan_revision(self) -> None:
        """Revise the plan, no RULING DUE."""
        swept, listed = sweep_and_next([graded(CHANGES, None, 1)])
        assert_that("RULING DUE" in swept, equal_to(False))
        assert_that(listed, contains_string("(revise the plan,"))

    def test_an_approved_pr_prints_neither(self) -> None:
        """No marker is printed for it, after any history."""
        for rounds in ([], RULED):
            swept, _ = sweep_and_next([*rounds, graded(APPROVED, APPROVED, 9)])
            assert_that("RULING DUE" in swept or "PAUSE" in swept, equal_to(False))

    def test_a_pr_without_rounds_is_offered_for_review(self) -> None:
        """The control: with no review comment, PR 3 is listed."""
        assert_that(sweep_and_next([])[1], contains_string("(review it"))

    def test_a_paused_pr_is_listed_for_nothing(self) -> None:
        """The label holds it, and it prints no line of the limit."""
        here = world_with([], labels=[{"name": "paused-owner"}])
        listed = [
            line for line in next_output(here).splitlines() if "project#3 (" in line
        ]
        assert_that(listed, equal_to([]))
        assert_that("RULING DUE" in sweep(here).out, equal_to(False))

    def test_the_ticket_of_a_held_pr_stays_taken(self) -> None:
        """The PR leaves the list; its ticket is not offered again."""
        here = world_with(TWO_PLAN_REJECTIONS, title="Fixes #9")
        out = next_output(here)
        assert_that("owner/project#9" in out, equal_to(False))

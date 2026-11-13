"""``pitboss sweep`` and ``slots next`` take their lines from the flow's step."""

import dataclasses
import functools
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import bodydigest, shapes
from . import (
    actreviewed,
    decisionline,
    fakes,
    fullpull,
    quietworld,
    test_flow,
    world,
    worldcomments,
)
from .test_commands import sweep
from .test_slot_commands import next_output
from . import blank

HEAD = "3" * 40
OLDER = "2" * 40
CHANGES = "changes needed"
APPROVED = "approved"
RULING_LINE = "RULING: owner/project#3: start an Opus agent"
PAUSE_LINE = "ORCHESTRATOR: owner/project#3: label the PR and its ticket paused-owner"
ESCALATES = "ORCHESTRATOR: owner/project#3: the Opus ruling escalated to the owner"
REVISE = "WORKER: owner/project#3: revise the PLAN only"
REVIEW_THIRD = "REVIEWER: owner/project#3: grade Plan and Execution together"
CONFLICT_THIRD = "WORKER: owner/project#3: resolve the conflict"
# PR 3's commits since main: authored at the older head, a fix of a.bats at HEAD
AUTHORED = {"sha": "1", "parents": [{"sha": "0"}]}
COMMITS: Mapping[str, object] = {
    f"{world.PROJECT}/compare/main...{HEAD}": {
        "commits": [AUTHORED, {"sha": "2", "parents": [{"sha": "1"}]}]
    },
    f"{world.PROJECT}/compare/main...{OLDER}": {"commits": [AUTHORED]},
    f"{world.PROJECT}/commits/2": {"files": [{"filename": "a.bats"}]},
}


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
    return blank.member_comment("\n".join(lines) + "\n", when)


def reading(review: shapes.Comment, body: str) -> shapes.Comment:
    """A review that records the digest of the PR body it read.

    Args:
        review: the review comment.
        body: the PR body it read.

    Returns:
        The comment with a ``Body:`` line after its ``Reviewed:`` line.
    """
    lines = review.body.splitlines()
    at = next(n for n, line in enumerate(lines) if line.startswith("Reviewed:")) + 1
    lines.insert(at, f"Body: {bodydigest.digest(body)}")
    return dataclasses.replace(review, body="\n".join(lines) + "\n")


def world_with(rounds: Sequence[shapes.Comment], **changes: object) -> world.World:
    """A world whose PR 3 has the comments.

    Args:
        rounds: the comments, as the API gives them.
        **changes: changes to PR 3's JSON (``head`` replaces the whole head).

    Returns:
        The world.
    """
    here = world.make_world()
    path = fakes.page("repos/owner/project/issues/3/comments")
    said = [world.comment_json(each) for each in rounds]
    here.bodies[path] = [*said, worldcomments.CLEAN_CHECK]
    changes.setdefault("head", {"sha": HEAD, "ref": "branch-3"})
    here.bodies[f"{world.PROJECT}/pulls/3"] = fakes.pull_body(3, **changes)
    # keyword: one-path: the open listing's row carries what the pull carries
    fakes.listed_row(here.bodies, world.PROJECT, 3, **fullpull.row_fields(changes))
    here.bodies.update(COMMITS)
    return quietworld.at_rest(with_complete_run(here))


def with_complete_run(here: world.World) -> world.World:
    """Give PR 3's head a dispatched run that completed before every review.

    An Execution review written before the run of its head finished does not
    count (pitboss#202), so the worlds whose reviews are meant to count have one.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    done = {"workflow_runs": [{"id": 5, "updated_at": "2026-01-01T00:00:00Z"}]}
    ran = {"check_runs": [world.GREEN]}
    for sha in (HEAD, OLDER):
        query = f"head_sha={sha}&event=workflow_dispatch&status=completed"
        path = f"{world.PROJECT}/actions/workflows/check.yml/runs?{query}"
        here.bodies[fakes.page(path)] = done
    return older_checks(here, ran)


def older_checks(here: world.World, body: Mapping[str, object]) -> world.World:
    """Serve the check runs of the older head of PR 3.

    Args:
        here: the world.
        body: the check runs page.

    Returns:
        The same world.
    """
    here.bodies[fakes.page(f"{world.PROJECT}/commits/{OLDER}/check-runs")] = body
    return here


def listed_for_third(here: world.World) -> Sequence[str]:
    """PR 3's decision line of ``slots next``.

    Args:
        here: the world.

    Returns:
        The line, none when PR 3 is in no answer.
    """
    found = decisionline.of(next_output(here), "owner/project#3")
    return [found] if found else []


def sweep_and_next(rounds: Sequence[shapes.Comment]) -> tuple[str, str]:
    """What the sweep prints, and PR 3's line of ``slots next``.

    Args:
        rounds: PR 3's comments.

    Returns:
        The sweep's output, and PR 3's line in the list (empty when none).
    """
    here = world_with(rounds)
    return sweep(here).out, "".join(listed_for_third(here))


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
    """The ruling, the pause, revise the plan, fix the review and review it."""

    def test_ruling_due_after_the_second_plan_rejection(self) -> None:
        """The ruling is the decision, in the sweep and in the list."""
        swept, listed = sweep_and_next(TWO_PLAN_REJECTIONS)
        assert_that(swept, contains_string(RULING_LINE))
        assert_that(PAUSE_LINE in swept, equal_to(False))
        assert_that(listed, contains_string(RULING_LINE))

    def test_ruling_due_after_the_fixed_execution_is_rejected_again(self) -> None:
        """The second execution rejection on the approved plan asks for a ruling."""
        swept, listed = sweep_and_next(EXECUTION_TWICE)
        assert_that(swept, contains_string(RULING_LINE))
        assert_that(listed, contains_string(RULING_LINE))

    def test_pause_after_the_ruling_and_another_plan_rejection(self) -> None:
        """The orchestrator posts the question to the owner: the decision."""
        swept, listed = sweep_and_next([*RULED, graded(CHANGES, None, 4)])
        assert_that(swept, contains_string(PAUSE_LINE))
        assert_that(RULING_LINE in swept, equal_to(False))
        assert_that(listed, contains_string(PAUSE_LINE))

    def test_pause_after_the_ruling_and_a_rejected_execution(self) -> None:
        """An execution rejection after the ruling pauses too."""
        rounds = [EXECUTION_TWICE[0], test_flow.ruling(2), graded(None, CHANGES, 3)]
        swept, listed = sweep_and_next(rounds)
        assert_that(swept, contains_string(PAUSE_LINE))
        assert_that(listed, contains_string(PAUSE_LINE))

    def test_a_review_that_approves_the_plan_and_asks_for_changes_is_a_ruling(
        self,
    ) -> None:
        """The ruling, and no fix round before it (keyword: ruling-first)."""
        swept, listed = sweep_and_next([graded(APPROVED, CHANGES, 1)])
        assert_that(swept, contains_string(RULING_LINE))
        assert_that(PAUSE_LINE in swept, equal_to(False))
        assert_that(listed, contains_string(RULING_LINE))

    def test_the_first_plan_rejection_is_a_plan_revision(self) -> None:
        """Revise the plan, no ruling."""
        swept, listed = sweep_and_next([graded(CHANGES, None, 1)])
        assert_that(RULING_LINE in swept, equal_to(False))
        assert_that(listed, contains_string(REVISE))

    def test_an_approved_pr_prints_neither(self) -> None:
        """Neither is decided for it, after any history."""
        for rounds in ([], RULED):
            swept, _ = sweep_and_next([*rounds, graded(APPROVED, APPROVED, 9)])
            assert_that(RULING_LINE in swept or PAUSE_LINE in swept, equal_to(False))

    def test_a_pr_without_rounds_is_offered_for_review(self) -> None:
        """The control: with no review comment, PR 3 is listed."""
        assert_that(sweep_and_next([])[1], contains_string(REVIEW_THIRD))

    def test_a_paused_pr_is_listed_for_nothing(self) -> None:
        """The label holds it, and it prints no line of the limit."""
        here = world_with([], labels=[{"name": "paused-owner"}])
        assert_that(listed_for_third(here), equal_to([]))
        assert_that(RULING_LINE in sweep(here).out, equal_to(False))

    def test_the_ticket_of_a_held_pr_stays_taken(self) -> None:
        """The PR is at its ruling; the ticket its body fixes is not offered again."""
        body = f"Fixes #9\n\n{fakes.PLAN_AND_EXECUTION}"
        here = world_with(TWO_PLAN_REJECTIONS, body=body)
        actreviewed.listed_body(here, 3, body)
        offered = decisionline.of(next_output(here), "owner/project#9")
        assert_that(offered, equal_to(""))


def ruled_by(line: str, second: int = 3) -> shapes.Comment:
    """A recorded Opus ruling of PR 3.

    Args:
        line: its second line.
        second: the second of the minute it was written.

    Returns:
        The comment.
    """
    return test_flow.ruling(second, line=line)


UNREADABLE_LINE = (
    "ORCHESTRATOR: owner/project#3: the newest Opus ruling has no readable"
)
DIRTY: Mapping[str, object] = {"mergeable_state": "dirty"}
UNREADABLE = ruled_by("no ruling line")
EXECUTION_APPROVED = ruled_by("Ruling: execution is approved")


class TestRulingNotInForm(unittest.TestCase):
    """An unreadable ruling is fixed, never paused (pitboss#129)."""

    def test_an_unreadable_ruling_is_named_not_paused(self) -> None:
        """The orchestrator has the ruling fixed; nothing is paused or ruled."""
        unknown = ruled_by("Ruling: whatever")
        worlds = {
            "no ruling line": world_with([*TWO_PLAN_REJECTIONS, UNREADABLE]),
            "unknown word": world_with([*TWO_PLAN_REJECTIONS, unknown]),
            "a review after it": world_with(
                [*RULED[:2], UNREADABLE, graded(CHANGES, None, 4)]
            ),
            "a draft at its plan stage": world_with([UNREADABLE], draft=True),
        }
        for name, here in worlds.items():
            with self.subTest(name):
                swept = sweep(here).out
                assert_that(swept, contains_string(UNREADABLE_LINE))
                shown = (PAUSE_LINE in swept, RULING_LINE in swept)
                assert_that(shown, equal_to((False, False)))
                listed = "".join(listed_for_third(here))
                assert_that(listed, contains_string(UNREADABLE_LINE))

    def test_the_newer_of_two_rulings_decides(self) -> None:
        """Unreadable after readable is unreadable; readable after unreadable is not."""
        readable = ruled_by("Ruling: split", 5)
        newer_bad, _ = sweep_and_next(
            [*TWO_PLAN_REJECTIONS, readable, ruled_by("x", 6)]
        )
        newer_ok, _ = sweep_and_next([*TWO_PLAN_REJECTIONS, ruled_by("x", 4), readable])
        assert_that(newer_bad, contains_string(UNREADABLE_LINE))
        assert_that(UNREADABLE_LINE in newer_ok, equal_to(False))


class TestRulingNoReviewFollows(unittest.TestCase):
    """PAUSE needs a review after a readable ruling (pitboss#129)."""

    def test_the_ruling_steps_are_offered_and_nothing_is_paused(self) -> None:
        """Each word is offered as the work it is, with no pause and no ruling."""
        carry = "WORKER: owner/project#3: do exactly what the Opus ruling says"
        cases = [
            ("do these steps", "WORKER: owner/project#3: do exactly the steps"),
            ("revise the plan", REVISE),
            ("split", carry),
            ("reshape", carry),
            ("abandon", carry),
        ]
        for word, kind in cases:
            with self.subTest(word=word):
                swept, listed = sweep_and_next(
                    [*TWO_PLAN_REJECTIONS, ruled_by(f"Ruling: {word}", 3)]
                )
                assert_that(PAUSE_LINE in swept, equal_to(False))
                assert_that(RULING_LINE in swept, equal_to(False))
                assert_that(listed, contains_string(kind))

    def test_escalating_prints_its_own_line_not_pause(self) -> None:
        """The owner is told, with a line that does not say a review failed."""
        rounds = [*TWO_PLAN_REJECTIONS, ruled_by("Ruling: escalate to the owner")]
        swept, listed = sweep_and_next(rounds)
        assert_that(swept, contains_string(ESCALATES))
        assert_that(PAUSE_LINE in swept, equal_to(False))
        assert_that(listed, contains_string(ESCALATES))

    def test_an_approved_execution_is_told_to_merge_or_resolve(self) -> None:
        """The merge while unarmed; disarm an arm with no record; the conflict."""
        armed: Mapping[str, object] = {"auto_merge": {"merge_method": "merge"}}
        merging = actreviewed.MERGING.format(number=3)
        cases: Sequence[tuple[Mapping[str, object], str, bool]] = [
            ({}, merging, True),
            (armed, merging, False),
            (
                armed,
                "ORCHESTRATOR: owner/project#3: `act disarm`, then `act arm`",
                True,
            ),
            (DIRTY, CONFLICT_THIRD, True),
        ]
        for changes, line, printed in cases:
            with self.subTest(line=line, changes=changes):
                here = world_with([*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED], **changes)
                quietworld.unheld(here)
                actreviewed.approve(here, 3)
                swept = sweep(here).out
                assert_that(line in swept, equal_to(printed))
                assert_that(PAUSE_LINE in swept, equal_to(False))

    def test_an_approved_execution_with_a_conflict_is_the_workers(self) -> None:
        """Listed as the conflict resolution, and not as a merge."""
        here = world_with([*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED], **DIRTY)
        assert_that("".join(listed_for_third(here)), contains_string(CONFLICT_THIRD))


def unfixed_rounds(*recorded: shapes.Comment, files: Sequence[str] = ()) -> world.World:
    """A world whose head moved from the rejected one by one commit.

    Args:
        *recorded: PR 3's comments.
        files: the paths the commit changes, none for an empty commit.

    Returns:
        The world.
    """
    moved = {"files": [{"filename": each} for each in files]}
    here = world_with(recorded)
    here.bodies.update({f"{world.PROJECT}/commits/2": moved})
    return here


def unfixed_after_the_ruling(files: Sequence[str] = ()) -> world.World:
    """An Execution rejected, ruled on, its Plan revised and approved alone.

    PR 3's head has no code the rejection has not seen but files (pitboss#390).

    Args:
        files: the paths the last commit changes.

    Returns:
        The world.
    """
    rejected = graded(APPROVED, CHANGES, 1, sha=OLDER)
    ruled = test_flow.ruling(2, line="Ruling: revise the plan")
    return unfixed_rounds(rejected, ruled, graded(APPROVED, None, 3), files=files)


approved_draft = functools.partial(world_with, [graded(APPROVED, None, 1)], draft=True)

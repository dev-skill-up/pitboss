"""``pitboss sweep`` and ``slots next`` take their lines from the flow's step."""

import dataclasses
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import bodydigest, rulingwords, shapes
from . import fakes, test_flow, world, worldcomments
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
    compare = f"{world.PROJECT}/compare/main..."
    authored = {"sha": "1", "parents": [{"sha": "0"}]}
    fix = {"sha": "2", "parents": [{"sha": "1"}]}
    here.bodies.update(
        {
            compare + HEAD: {"commits": [authored, fix]},
            compare + OLDER: {"commits": [authored]},
            f"{world.PROJECT}/commits/2": {"files": [{"filename": "a.bats"}]},
        }
    )
    return with_complete_run(here)


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
    """PR 3's lines of ``slots next``.

    Args:
        here: the world.

    Returns:
        The lines, none when PR 3 is offered for nothing.
    """
    return [line for line in next_output(here).splitlines() if "project#3 (" in line]


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

    def test_a_review_that_approves_the_plan_and_asks_for_changes_is_a_ruling(
        self,
    ) -> None:
        """RULING DUE, and no fix round before it (keyword: ruling-first)."""
        swept, listed = sweep_and_next([graded(APPROVED, CHANGES, 1)])
        assert_that(swept, contains_string(RULING_LINE))
        assert_that("PAUSE" in swept, equal_to(False))
        assert_that(listed, equal_to(""))

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
        assert_that(listed_for_third(here), equal_to([]))
        assert_that("RULING DUE" in sweep(here).out, equal_to(False))

    def test_the_ticket_of_a_held_pr_stays_taken(self) -> None:
        """The PR leaves the list; its ticket is not offered again."""
        here = world_with(TWO_PLAN_REJECTIONS, title="Fixes #9")
        out = next_output(here)
        assert_that("owner/project#9" in out, equal_to(False))


def ruled_by(line: str, second: int = 3) -> shapes.Comment:
    """A recorded Opus ruling of PR 3.

    Args:
        line: its second line.
        second: the second of the minute it was written.

    Returns:
        The comment.
    """
    return test_flow.ruling(second, line=line)


UNREADABLE_LINE = "RULING UNREADABLE owner/project#3: https://example.org/ruling/"
DIRTY: Mapping[str, object] = {"mergeable_state": "dirty"}
UNREADABLE = ruled_by("no ruling line")
EXECUTION_APPROVED = ruled_by("Ruling: execution is approved")


class TestRulingNotInForm(unittest.TestCase):
    """An unreadable ruling is fixed, never paused (pitboss#129)."""

    def test_an_unreadable_ruling_is_named_not_paused(self) -> None:
        """The comment and the words are named; the PR is offered for nothing."""
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
                assert_that(swept, contains_string(f"one of: {rulingwords.WORDS};"))
                shown = ("PAUSE owner" in swept, "RULING DUE" in swept)
                assert_that(shown, equal_to((False, False)))
                assert_that(listed_for_third(here), equal_to([]))

    def test_the_newer_of_two_rulings_decides(self) -> None:
        """Unreadable after readable is unreadable; readable after unreadable is not."""
        readable = ruled_by("Ruling: split", 5)
        newer_bad, _ = sweep_and_next(
            [*TWO_PLAN_REJECTIONS, readable, ruled_by("x", 6)]
        )
        newer_ok, _ = sweep_and_next([*TWO_PLAN_REJECTIONS, ruled_by("x", 4), readable])
        assert_that(newer_bad, contains_string(UNREADABLE_LINE))
        assert_that("RULING UNREADABLE" in newer_ok, equal_to(False))


class TestRulingNoReviewFollows(unittest.TestCase):
    """PAUSE needs a review after a readable ruling (pitboss#129)."""

    def test_the_ruling_steps_are_offered_and_nothing_is_paused(self) -> None:
        """Each word is offered as the work it is, with no PAUSE or RULING DUE."""
        cases = [
            ("do these steps", "(do the ruling's steps,"),
            ("revise the plan", "(revise the plan,"),
            ("split", "(carry out the ruling,"),
            ("reshape", "(carry out the ruling,"),
            ("abandon", "(carry out the ruling,"),
        ]
        for word, kind in cases:
            with self.subTest(word=word):
                swept, listed = sweep_and_next(
                    [*TWO_PLAN_REJECTIONS, ruled_by(f"Ruling: {word}", 3)]
                )
                assert_that("PAUSE owner" in swept, equal_to(False))
                assert_that("RULING DUE" in swept, equal_to(False))
                assert_that(listed, contains_string(kind))

    def test_escalating_prints_its_own_line_not_pause(self) -> None:
        """The owner is told, with a line that does not say a review failed."""
        rounds = [*TWO_PLAN_REJECTIONS, ruled_by("Ruling: escalate to the owner")]
        swept, listed = sweep_and_next(rounds)
        assert_that(
            swept,
            contains_string("RULING ESCALATES owner/project#3: the Opus ruling esc"),
        )
        assert_that("PAUSE owner" in swept, equal_to(False))
        assert_that(listed, equal_to(""))

    def test_an_approved_execution_is_told_to_merge_or_resolve(self) -> None:
        """READY TO MERGE while auto-merge is off; none when armed; the conflict."""
        armed: Mapping[str, object] = {"auto_merge": {"merge_method": "merge"}}
        cases: Sequence[tuple[Mapping[str, object], str, bool]] = [
            ({}, "READY TO MERGE owner/project#3", True),
            (armed, "READY TO MERGE owner/project#3", False),
            (armed, "AUTO MERGE OFF owner/project#3", False),
            (DIRTY, "CONFLICT owner/project#3", True),
        ]
        for changes, line, printed in cases:
            with self.subTest(line=line, changes=changes):
                here = world_with([*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED], **changes)
                swept = sweep(here).out
                assert_that(line in swept, equal_to(printed))
                assert_that("PAUSE owner" in swept, equal_to(False))

    def test_an_approved_execution_with_a_conflict_is_the_workers(self) -> None:
        """Listed as the conflict resolution, and not as a merge."""
        here = world_with([*TWO_PLAN_REJECTIONS, EXECUTION_APPROVED], **DIRTY)
        assert_that(
            "".join(listed_for_third(here)), contains_string("(resolve the conflict,")
        )


class TestBodyFix(unittest.TestCase):
    """The history of pitboss#146: a body fix between two rejections of one head."""

    def test_ruling_due_after_a_body_fix_between_two_rejections_at_one_head(
        self,
    ) -> None:
        """The #146 history: two reviews of one head, the body edited between."""
        now = "Fixes #1\n\n## Plan\nthe plan\n\n## Execution\nthe fixed work\n"
        before = "Fixes #1\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"
        rounds = [
            reading(graded(APPROVED, CHANGES, 1), before),
            reading(graded(APPROVED, CHANGES, 2), now),
        ]
        here = world_with(rounds, body=now)
        assert_that(sweep(here).out, contains_string(RULING_LINE))
        assert_that(listed_for_third(here), equal_to([]))
        assert_that(
            next_output(here),
            contains_string("make an Opus ruling: owner/project#3: Opus agent"),
        )


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

    PR 3's head carries no code the rejection has not seen, but for files
    (keyword: unfixed-execution, pitboss#390).

    Args:
        files: the paths the last commit changes.

    Returns:
        The world.
    """
    rejected = graded(APPROVED, CHANGES, 1, sha=OLDER)
    ruled = test_flow.ruling(2, line="Ruling: revise the plan")
    return unfixed_rounds(rejected, ruled, graded(APPROVED, None, 3), files=files)

"""Tests for the changes-needed limit: RULING DUE and PAUSE."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, pulls, reviews, roundlimit, shapes, work
from . import fakes, test_work, world
from .test_commands import sweep
from .test_slot_commands import next_output

SETTINGS = fakes.settings(fakes.directory())
FORM = SETTINGS.review.form
REVIEW = dataclasses.replace(
    SETTINGS.review, gated=frozenset({"owner/gated"}), trusted=frozenset({"MEMBER"})
)
NONE = roundlimit.Limit.NONE
DUE = roundlimit.Limit.RULING_DUE
PAUSE = roundlimit.Limit.PAUSE
PLAN_REJECTED = ("changes needed", "changes needed")
PLAN_APPROVED_EXECUTION_REJECTED = ("approved", "changes needed")
ALL_APPROVED = ("approved", "approved")
NO_PLAN_LINE = "no plan line"
RULING = "Opus ruling\nThe rounds disagree about the plan; take the second reading."


def comment(body: str, second: int, author: str = "MEMBER") -> shapes.Comment:
    """An issue comment.

    Args:
        body: its text.
        second: the second of the minute it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    return shapes.Comment(
        body=body,
        author_association=author,
        created_at=f"2026-10-30T00:00:{second:02d}Z",
    )


def graded(
    plan: str, verdict: str, second: int, author: str = "MEMBER"
) -> shapes.Comment:
    """A review comment in the default form, with a Plan line.

    Args:
        plan: the plan grade, or ``no plan line`` to leave the line out.
        verdict: the verdict word.
        second: the second of the minute it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    plan_line = "" if plan == NO_PLAN_LINE else f"Plan: {plan}\n"
    body = f"## Review\nReviewed: {'a' * 40}\n{plan_line}Verdict: {verdict}\n"
    return comment(body, second, author)


def ruling(second: int, author: str = "MEMBER") -> shapes.Comment:
    """A recorded ruling.

    Args:
        second: the second of the minute it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    return comment(RULING, second, author)


def limit_after(
    *posted: shapes.Comment, slug: str = "owner/project"
) -> roundlimit.Limit:
    """The limit the comments leave, read as the sweep reads them.

    Args:
        *posted: the comments.
        slug: the repository.

    Returns:
        The limit.
    """
    holder = pulls.Source(github=fakes.github({}), review=REVIEW)
    return pulls.limit_of(holder, config.make_repo("owner", slug.split("/")[1]), posted)


def limits_as_posted(comments: Sequence[shapes.Comment]) -> Sequence[roundlimit.Limit]:
    """The limit after each comment, one at a time.

    Args:
        comments: the comments, oldest first.

    Returns:
        The limits.
    """
    return [limit_after(*comments[: count + 1]) for count in range(len(comments))]


REACHED = [graded(*PLAN_REJECTED, 1), graded(*PLAN_APPROVED_EXECUTION_REJECTED, 2)]


class TestReading(unittest.TestCase):
    """The rounds, from the comments."""

    def test_plan_rejected_once_then_approved_with_changes_needed(self) -> None:
        """No marker for the first rejection, RULING DUE at the second review."""
        assert_that(limits_as_posted(REACHED), equal_to([NONE, DUE]))

    def test_a_ruling_then_another_changes_needed_is_a_pause(self) -> None:
        """The ruling clears RULING DUE; the next changes needed is PAUSE."""
        posted = [*REACHED, ruling(3), graded("approved", "changes needed", 4)]
        assert_that(limits_as_posted(posted), equal_to([NONE, DUE, NONE, PAUSE]))

    def test_an_approved_pr_prints_neither(self) -> None:
        """Approval of plan and execution is no marker, after any history."""
        approved = graded(*ALL_APPROVED, 9)
        found = [
            limit_after(graded(*ALL_APPROVED, 1)),
            limit_after(*REACHED, approved),
            limit_after(*REACHED, ruling(5), approved),
        ]
        assert_that(found, equal_to([NONE, NONE, NONE]))

    def test_two_plan_rejections_call_for_a_ruling(self) -> None:
        """A plan that is not approved after two reviews is RULING DUE."""
        posted = [graded(*PLAN_REJECTED, 1), graded(*PLAN_REJECTED, 2)]
        assert_that(limits_as_posted(posted), equal_to([NONE, DUE]))

    def test_a_ruling_after_the_last_review_leaves_nothing_due(self) -> None:
        """Until the next review, a recorded ruling is the wait's end."""
        posted = [graded(*PLAN_REJECTED, 1), graded(*PLAN_REJECTED, 2), ruling(3)]
        assert_that(limit_after(*posted), equal_to(NONE))

    def test_any_changes_needed_after_the_ruling_pauses(self) -> None:
        """A plan rejection after the ruling pauses too."""
        posted = [graded(*PLAN_REJECTED, 1), graded(*PLAN_REJECTED, 2), ruling(3)]
        posted.append(graded(*PLAN_REJECTED, 4))
        assert_that(limit_after(*posted), equal_to(PAUSE))

    def test_reviews_without_a_plan_line_say_nothing_of_the_plan(self) -> None:
        """Changes needed with no Plan line is neither a rejection nor an approval."""
        posted = [
            graded(NO_PLAN_LINE, "changes needed", number) for number in (1, 2, 3)
        ]
        assert_that(limit_after(*posted), equal_to(NONE))

    def test_a_plan_rejection_after_the_approval_is_not_counted(self) -> None:
        """Only the grades before the approval are plan rejections."""
        posted = [graded(*ALL_APPROVED, 1), graded("changes needed", "approved", 2)]
        assert_that(limit_after(*posted), equal_to(NONE))

    def test_the_comments_are_read_in_the_order_written(self) -> None:
        """The newest review decides, whatever order the API listed them in."""
        assert_that(limit_after(REACHED[1], REACHED[0]), equal_to(DUE))

    def test_untrusted_comments_count_for_nothing(self) -> None:
        """A review or a ruling by an outsider is ignored."""
        outsider = graded(*PLAN_APPROVED_EXECUTION_REJECTED, 2, author="NONE")
        found = [
            limit_after(graded(*PLAN_REJECTED, 1), outsider),
            limit_after(REACHED[1], ruling(3, "NONE")),
        ]
        assert_that(found, equal_to([NONE, DUE]))

    def test_a_comment_that_is_no_review_is_skipped(self) -> None:
        """Chatter changes nothing."""
        assert_that(limit_after(REACHED[1], comment("thanks", 3)), equal_to(DUE))

    def test_a_gated_repository_reads_the_strict_form(self) -> None:
        """The same rounds are read in a gated repository."""
        found = limit_after(REACHED[1], slug="owner/gated")
        assert_that(found, equal_to(DUE))


class TestForms(unittest.TestCase):
    """The two lines the sweep reads besides the review's form."""

    def test_the_first_line_of_a_ruling_is_opus_ruling(self) -> None:
        """Only that exact first line records a ruling."""
        bodies = ["Opus ruling", "Opus ruling  \nmore", "Opus ruling: take it"]
        bodies += ["opus ruling", "The Opus ruling", ""]
        found = [roundlimit.is_ruling(body) for body in bodies]
        assert_that(found, equal_to([True, True, False, False, False, False]))

    def test_the_plan_line_is_graded_by_the_forms_words(self) -> None:
        """Approved, changes needed, or no Plan line."""
        bodies = ["Plan: approved", "x\nPlan: changes needed  \nVerdict: approved"]
        bodies += ["Plan: approved of it", "Plan:approved", "nothing"]
        found = [roundlimit.plan_grade(body, FORM) for body in bodies]
        grades = shapes.Verdict
        none = None
        expected = [grades.APPROVED, grades.CHANGES_NEEDED, none, none, none]
        assert_that(found, equal_to(expected))


def world_with(rounds: Sequence[shapes.Comment]) -> world.World:
    """A world whose PR 3 has the comments.

    Args:
        rounds: the comments, as the API gives them.

    Returns:
        The world.
    """
    here = world.make_world()
    path = fakes.page("repos/owner/project/issues/3/comments")
    here.bodies[path] = [
        {
            "body": each.body.replace("a" * 40, "3" * 40),
            "author_association": each.author_association,
            "created_at": each.created_at,
        }
        for each in rounds
    ]
    return here


def sweep_and_next(rounds: Sequence[shapes.Comment]) -> tuple[str, bool]:
    """What the sweep prints, and whether ``slots next`` lists PR 3.

    Args:
        rounds: PR 3's comments.

    Returns:
        The sweep's output, and whether PR 3 has a line in the list.
    """
    here = world_with(rounds)
    return sweep(here).out, "owner/project#3 (" in next_output(here)


RULING_LINE = "RULING DUE owner/project#3: the review rounds hit"
PAUSE_LINE = "PAUSE owner/project#3: changes needed again after the Opus ruling"


class TestSweepAndNext(unittest.TestCase):
    """``pitboss sweep`` prints the marker; ``pitboss slots next`` leaves the PR out."""

    def test_ruling_due(self) -> None:
        """RULING DUE is printed, and PR 3 is not offered for a review."""
        swept, listed = sweep_and_next(REACHED)
        assert_that(swept, contains_string(RULING_LINE))
        assert_that("PAUSE owner" in swept, equal_to(False))
        assert_that(listed, equal_to(False))

    def test_pause(self) -> None:
        """PAUSE is printed after a ruling and another changes needed."""
        rounds = [*REACHED, ruling(3), graded("approved", "changes needed", 4)]
        swept, listed = sweep_and_next(rounds)
        assert_that(swept, contains_string(PAUSE_LINE))
        assert_that("RULING DUE" in swept, equal_to(False))
        assert_that(listed, equal_to(False))

    def test_an_approved_pr_prints_neither(self) -> None:
        """No marker is printed for it."""
        swept, _ = sweep_and_next([graded(*ALL_APPROVED, 1)])
        assert_that("RULING DUE" in swept or "PAUSE" in swept, equal_to(False))

    def test_a_pr_without_rounds_is_still_offered_for_review(self) -> None:
        """The control: with no review comment, PR 3 is listed."""
        assert_that(sweep_and_next([])[1], equal_to(True))

    def test_the_ticket_of_a_held_pr_stays_taken(self) -> None:
        """The PR leaves the list; its ticket is not offered again."""
        held = dataclasses.replace(
            test_work.facts(3, reviews.Standing.CHANGES_NEEDED, body="Fixes #9"),
            limit=DUE,
        )
        assert_that(work.pull_items([held], SETTINGS), equal_to([]))
        assert_that("owner/project#9" in work.taken([held]), equal_to(True))

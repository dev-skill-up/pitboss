"""A review with a Plan line and no Execution line is no approval (pitboss#201).

The comments of bats-lang/repository-prototype#573 are played: two Plan
rejections, an Opus ruling ``do these steps``, then a review that wrote
``Plan: approved. The Plan's audit row now ...`` (the grade word followed by the
reviewer's own words), ``Verdict: approved`` and no ``Execution:`` line. The
sweep printed READY TO MERGE for it, and ``pitboss next`` offered the Plan
review again.
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import gradeline, reviews, shapes, steps
from . import test_flow, test_flow_sweep, world
from .test_commands import sweep

HEAD = test_flow_sweep.HEAD
PROSE_PLAN = "Plan: approved. The audit row now takes its list from the run."
FIRST = f"## Review\nReviewed: {HEAD}\n"
PLAN_ONLY_BODY = f"{FIRST}{PROSE_PLAN}\nVerdict: approved\n"
UNGRADED_BODY = f"{FIRST}Plan: fine\nVerdict: approved\n"
READY = "READY TO MERGE owner/project#3"
UNWRITTEN = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nNot started: later\n"
REVIEW = test_flow.REVIEW


def plan_only(body: str) -> shapes.Comment:
    """The Plan-only approval of #573, written after the ruling.

    Args:
        body: the comment.

    Returns:
        The comment.
    """
    when = "2026-10-30T00:00:04Z"
    return shapes.Comment(body=body, author_association="MEMBER", created_at=when)


def played(body: str) -> Sequence[shapes.Comment]:
    """The comments of #573: two rejections, the ruling, the approval.

    Args:
        body: the approval's text.

    Returns:
        The comments.
    """
    return [*test_flow_sweep.RULED, plan_only(body)]


def newest(body: str) -> reviews.Found:
    """The review a comment is read as.

    Args:
        body: the comment.

    Returns:
        The review.
    """
    read, form = reviews.rules(REVIEW, "owner/project")
    posted = [plan_only(body)]
    return next(iter(reviews.from_comments(posted, REVIEW.trusted, read, form)))


def next_printed(
    comments: Sequence[shapes.Comment], draft: bool = True, body: str = UNWRITTEN
) -> str:
    """What ``pitboss next`` prints for PR 3 (a draft or not) with the comments.

    Args:
        comments: PR 3's comments.
        draft: whether PR 3 is a draft.
        body: PR 3's body, whose Execution is a placeholder by default.

    Returns:
        The output.
    """
    here = test_flow_sweep.world_with(comments, body=body, draft=draft)
    return world.invoke(here, "next", here.config, "#7", "--now", world.FUTURE).out


def assert_worker_round_not_the_review(draft: bool) -> None:
    """Assert ``next`` prints the worker round and no review, draft or not.

    Args:
        draft: whether PR 3 is a draft.
    """
    want = steps.describe(steps.worker(steps.Task.RUN_PLAN))
    printed = next_printed(played(PLAN_ONLY_BODY), draft=draft)
    assert_that(printed, contains_string(want))
    assert_that("REGULAR_REVIEW" in printed, equal_to(False))


class TestReading(unittest.TestCase):
    """What the review of #573 is read as."""

    def test_a_grade_word_then_a_full_stop_and_words_grades(self) -> None:
        """Approved, changes needed; a word glued to others grades nothing."""
        words = ("approved", "changes needed")
        lines = (
            PROSE_PLAN,
            "Plan: changes needed, the list is short",
            "Plan: approvedly",
            "Plan: changes needed (fixed)",
            "Plan: approved",
            "Plan: approved; the row is there",
            "Plan: approved Review of the Plan alone, second round",
            "Plan: changes needed the list is short",
        )
        found = [gradeline.line_approved(each, "Plan: ", *words) for each in lines]
        assert_that(found, equal_to([True, False, None, None, True, True, True, False]))

    def test_a_plan_line_is_present_whatever_it_says(self) -> None:
        """A line that starts with ``Plan:`` counts; another does not."""
        bodies = ("Plan: fine\n", "Reviewed: x\nPlan:\n", "The Plan: x\n")
        found = [gradeline.present(each, "Plan: ") for each in bodies]
        assert_that(found, equal_to([True, True, False]))

    def test_a_plan_line_and_no_execution_line_is_no_approval_to_merge(self) -> None:
        """Graded or not, the standing is the plan's, never an approval."""
        approved, ungraded = newest(PLAN_ONLY_BODY), newest(UNGRADED_BODY)
        assert_that(
            (approved.plan_approved, approved.plan_alone, ungraded.plan_alone),
            equal_to((True, True, True)),
        )
        standings = [reviews.head_standing(each, HEAD) for each in (approved, ungraded)]
        assert_that(standings, equal_to([reviews.Standing.PLAN_APPROVED] * 2))


class TestTrailingText(unittest.TestCase):
    """A Plan line with text after the verdict is read as the verdict (#255)."""

    def test_next_prints_the_same_for_both_forms(self) -> None:
        """Done-when 2: ``pitboss next`` reads the same verdict from both."""
        bare = f"{FIRST}Plan: approved\nVerdict: approved\n"
        text = f"{FIRST}Plan: approved Review of the Plan alone\nVerdict: approved\n"
        first, second = next_printed(played(bare)), next_printed(played(text))
        assert_that(second, equal_to(first))
        assert_that(first, equal_to(next_printed(played(PLAN_ONLY_BODY))))

    def test_sweep_reads_the_same_verdict_from_both_forms(self) -> None:
        """Done-when 2: the sweep reads the same standing from both forms."""
        bare = f"{FIRST}Plan: approved\nVerdict: approved\n"
        text = f"{FIRST}Plan: approved Review of the Plan alone\nVerdict: approved\n"
        first = sweep(test_flow_sweep.world_with(played(bare))).out
        second = sweep(test_flow_sweep.world_with(played(text))).out
        assert_that(first, contains_string("review=plan-approved"))
        assert_that(second, contains_string("review=plan-approved"))
        assert_that(READY in first, equal_to(False))
        assert_that(READY in second, equal_to(False))

    def test_review_form_prints_the_plan_line(self) -> None:
        """Done-when 3: the form says the exact Plan line."""
        here = world.make_world()
        printed = world.again(here, "review-form", "gated").out
        assert_that(printed, contains_string(gradeline.FORM_LINE))
        assert_that(printed, contains_string(gradeline.FORM_NOTE))


class TestSweepAndNext(unittest.TestCase):
    """The lines of the ticket's Done-when, played on the comments of #573."""

    def test_the_sweep_prints_no_ready_to_merge(self) -> None:
        """Done-when 1: a Plan-only approval, green and clean, is not ready."""
        swept = sweep(test_flow_sweep.world_with(played(PLAN_ONLY_BODY))).out
        assert_that(READY in swept, equal_to(False))
        assert_that(swept, contains_string("review=plan-approved"))
        here = test_flow_sweep.world_with(played(UNGRADED_BODY))
        assert_that(READY in sweep(here).out, equal_to(False))

    def test_next_prints_the_worker_round_and_not_the_plan_review(self) -> None:
        """Done-when 1 and 2: the Plan approved after the ruling is not regraded."""
        assert_worker_round_not_the_review(draft=True)

    def test_next_prints_the_worker_round_for_a_pr_that_is_not_a_draft(self) -> None:
        """Done-when 1 with no condition on the draft: the same round."""
        assert_worker_round_not_the_review(draft=False)

    def test_a_filled_execution_is_reviewed_not_run_again(self) -> None:
        """pitboss#390: nothing to fill and no command to check, so no worker."""
        printed = next_printed(played(PLAN_ONLY_BODY), False, test_flow.BODY)
        assert_that(printed, contains_string("REGULAR_REVIEW: #7"))
        run = steps.describe(steps.worker(steps.Task.RUN_PLAN))
        assert_that(run in printed, equal_to(False))

    def test_the_worker_round_needs_a_ruling_before_the_approval(self) -> None:
        """With no ruling, a Plan approved alone is the ordinary draft's."""
        printed = next_printed([plan_only(PLAN_ONLY_BODY)])
        assert_that("RUN_PLAN" in printed, equal_to(False))
        assert_that(printed, contains_string("UNDRAFT"))

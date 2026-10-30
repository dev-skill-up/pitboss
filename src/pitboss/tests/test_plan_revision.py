"""Tests for the plan revision round (keyword: plan-revision, pitboss#82)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import gradeline, pulls, reviews, shapes, work
from . import fakes, test_commands, test_pulls, test_work, world

APPROVED = reviews.Verdict.APPROVED
CHANGES = reviews.Verdict.CHANGES_NEEDED
STANDING = reviews.Standing
KINDS = work.Category
HEAD = "3" * 40
AFTER = ("--now", world.FUTURE)
COMMENTS = fakes.page("repos/owner/project/issues/3/comments")


def review_comment(
    verdict: str, plan: str | None, execution: str | None
) -> shapes.Comment:
    """A review comment in the default form with the lines given.

    Args:
        verdict: the verdict word.
        plan: the plan grade, or None for no ``Plan:`` line.
        execution: the execution grade, or None for no ``Execution:`` line.

    Returns:
        The comment.
    """
    lines = [
        "## Review",
        f"Reviewed: {'a' * 40}",
        *([f"Plan: {plan}"] if plan else []),
        *([f"Execution: {execution}"] if execution else []),
        f"Verdict: {verdict}",
    ]
    return shapes.Comment(
        body="\n".join(lines).replace("a" * 40, HEAD) + "\n",
        author_association="MEMBER",
        created_at="2026-10-30T00:00:01Z",
    )


def world_with(posted: shapes.Comment) -> world.World:
    """A world whose PR 3 has the one comment.

    Args:
        posted: the comment.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies[COMMENTS] = [
        {
            "body": posted.body,
            "author_association": posted.author_association,
            "created_at": posted.created_at,
            "html_url": posted.url,
        }
    ]
    return here


def outputs(posted: shapes.Comment) -> tuple[str, str, str]:
    """What the sweep and ``slots next`` print for a world with PR 3's comment.

    Args:
        posted: PR 3's only comment.

    Returns:
        The sweep, PR 3's line of it, and PR 3's line of ``slots next``.
    """
    here = world_with(posted)
    swept = world.invoke(here, "sweep", here.config, *AFTER).out
    listed = world.invoke(here, "slots", "next", here.config, *AFTER).out
    return (
        swept,
        next(line for line in swept.splitlines() if "owner/project#3 [" in line),
        "".join(line for line in listed.splitlines() if "project#3 (" in line),
    )


def review_of(
    verdict: reviews.Verdict, plan: bool | None, alone: bool
) -> reviews.Standing:
    """Where the head stands with a review that has the grades given.

    Args:
        verdict: the review's verdict.
        plan: its plan grade.
        alone: whether it grades the plan alone.

    Returns:
        The standing.
    """
    found = reviews.Found(
        sha=HEAD, verdict=verdict, when="", plan_approved=plan, plan_alone=alone
    )
    return reviews.head_standing(found, HEAD)


class TestHeadStanding(unittest.TestCase):
    """Where a head stands with a review that grades the plan."""

    def test_a_rejected_plan(self) -> None:
        """Plan changes needed is its own standing, whatever the execution."""
        found = [review_of(CHANGES, False, alone) for alone in (False, True)]
        assert_that(found, equal_to([STANDING.PLAN_CHANGES_NEEDED] * 2))

    def test_a_plan_approved_alone(self) -> None:
        """Only an approval of the plan with no execution grade is plan approved."""
        found = [
            review_of(APPROVED, True, True),
            review_of(APPROVED, True, False),
            review_of(APPROVED, False, True),
            review_of(APPROVED, None, False),
        ]
        expected = [STANDING.PLAN_APPROVED, *[STANDING.APPROVED] * 3]
        assert_that(found, equal_to(expected))

    def test_changes_needed_with_the_plan_approved_or_unsaid(self) -> None:
        """The usual standing: a fix of the review."""
        found = [review_of(CHANGES, True, False), review_of(CHANGES, None, False)]
        assert_that(found, equal_to([STANDING.CHANGES_NEEDED] * 2))


class TestReadingLines(unittest.TestCase):
    """The Plan and Execution lines of a review comment."""

    def test_grade_lines(self) -> None:
        """A line grades with the form's two words; another word grades nothing."""
        body = "Plan: changes needed\nExecution: approved\nVerdict: approved\n"
        words = ("approved", "changes needed")
        found = [
            gradeline.line_approved(body, gradeline.PLAN_PREFIX, *words),
            gradeline.line_approved(body, gradeline.EXECUTION_PREFIX, *words),
            gradeline.line_approved("Plan: fine\n", gradeline.PLAN_PREFIX, *words),
        ]
        assert_that(found, equal_to([False, True, None]))

    def test_newest_has_the_grades_of_its_comment(self) -> None:
        """A review comment has a plan grade; a GitHub review has none."""
        alone = review_comment("changes needed", "changes needed", None)
        full = review_comment("approved", "approved", "approved")
        github = shapes.PullReview(
            state="CHANGES_REQUESTED",
            commit_id=HEAD,
            author_association="MEMBER",
            submitted_at="1",
        )
        sources = [
            reviews.Sources(comments=comments, reviews=submitted)
            for comments, submitted in [([alone], []), ([full], []), ([], [github])]
        ]
        review = fakes.settings(fakes.directory()).review
        found = [reviews.newest(each, review, "owner/project") for each in sources]
        read = [(each.plan_approved, each.plan_alone) for each in found if each]
        expected = [(False, True), (True, False), (None, False)]
        assert_that(read, equal_to(expected))


class TestKinds(unittest.TestCase):
    """The kind of work a PR is listed as."""

    def test_newest_review_decides_the_kind(self) -> None:
        """Plan changes needed: revise the plan; otherwise fix the review."""
        open_pulls: Sequence[pulls.PullFacts] = [
            test_work.facts(1, review_of(CHANGES, False, False)),
            test_work.facts(2, review_of(CHANGES, True, False)),
            test_work.facts(3, review_of(CHANGES, None, False)),
            test_work.facts(4, review_of(APPROVED, True, True)),
            test_work.facts(5, review_of(APPROVED, True, True), draft=True),
        ]
        found = [
            (each.reference, each.category)
            for each in work.pull_items(open_pulls, fakes.settings(fakes.directory()))
        ]
        expected = [KINDS.REVISE_PLAN, KINDS.FIX_REVIEW, KINDS.FIX_REVIEW, KINDS.REVIEW]
        names = [f"owner/project#{number}" for number in range(1, 5)]
        assert_that(found, equal_to(list(zip(names, expected))))


NEEDED = "changes needed"
OUTPUT_CASES = [
    # (verdict, plan, execution), the PR line, the kind listed, ready to merge
    ((NEEDED, NEEDED, NEEDED), "review=plan-changes-needed", "(revise the plan,", 0),
    ((NEEDED, None, NEEDED), "review=changes-needed", "(fix the review,", 0),
    ((NEEDED, "approved", NEEDED), "review=changes-needed", "", 0),
    (("approved", "approved", None), "review=plan-approved", "(review it", 0),
    (("approved", "approved", "approved"), "review=approved-this-head", "", 1),
]


class TestSweepAndNext(unittest.TestCase):
    """The sweep's PR line and ``slots next``, from the comments."""

    def test_each_review_has_its_line_and_kind(self) -> None:
        """A rejected plan is revised, a plan approved alone is no approval to merge.

        A review that approves the plan and asks for changes is held by the
        limit (RULING DUE), so it is listed as no kind.
        """
        for grades, line, kind, ready in OUTPUT_CASES:
            swept, pull_line, listed = outputs(review_comment(*grades))
            merges = "READY TO MERGE owner/project#3" in swept
            assert_that(
                (line in pull_line, kind in listed and bool(listed) == bool(kind)),
                equal_to((True, True)),
            )
            assert_that(merges, equal_to(bool(ready)))

    def test_a_plan_approved_alone_gets_no_auto_merge_line(self) -> None:
        """Auto-merge is never armed on an approval of the plan alone.

        The control is a review that also grades the execution: that head is
        told to arm auto-merge again (it is not clean, so it is not ready), so
        the line is not missing for another reason.
        """
        armed = []
        for posted in (
            review_comment("approved", "approved", None),
            review_comment("approved", "approved", "approved"),
        ):
            here = world_with(posted)
            test_commands.unclean_third(here)
            swept = world.invoke(here, "sweep", here.config, *AFTER).out
            armed.append("AUTO MERGE OFF owner/project#3" in swept)
        assert_that(armed, equal_to([False, True]))


class TestCarryOver(unittest.TestCase):
    """An approval of the plan alone is not carried over merges of the base."""

    def test_older_plan_approval_is_not_an_approval(self) -> None:
        """Only merges since the head it named: the standing is the older head's."""
        for plan_line, expected in [
            ("", STANDING.APPROVED_BEFORE_MERGES),
            ("Plan: approved\n", STANDING.OLDER_HEAD),
        ]:
            found = test_pulls.bodies([test_pulls.AUTHORED, test_pulls.MERGE])
            comment = dict(test_pulls.OLD_GATED_APPROVAL)
            comment["body"] = str(comment["body"]).replace(
                "Verdict:", plan_line + "Verdict:"
            )
            found[fakes.page("repos/owner/project/issues/1/comments")] = [comment]
            project, _ = test_pulls.read(found)
            assert_that(project.standing, equal_to(expected))

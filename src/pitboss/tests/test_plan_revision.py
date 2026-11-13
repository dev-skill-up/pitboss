"""Tests for the plan revision round (keyword: plan-revision, pitboss#82)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import gradeline, reviews, shapes, work
from . import decisionline, fakes, quietworld, test_commands, test_pulls, world
from .actreviewed import TO_REVIEW

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
    here.bodies[COMMENTS] = [world.comment_json(posted)]
    return quietworld.at_rest(here)


def outputs(posted: shapes.Comment) -> tuple[str, str]:
    """PR 3's line of the sweep and its decision, in a world with its comment.

    Args:
        posted: PR 3's only comment.

    Returns:
        PR 3's state line of the sweep, and its decision.
    """
    here = quietworld.calm(world_with(posted))
    swept = world.invoke(here, "sweep", here.config, *AFTER).out
    return (
        next(line for line in swept.splitlines() if "owner/project#3 [" in line),
        decisionline.of(swept, "owner/project#3"),
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


NEEDED = "changes needed"
OUTPUT_CASES = [
    # (verdict, plan, execution), the PR line, PR 3's decision
    ((NEEDED, NEEDED, NEEDED), "review=plan-changes-needed", "revise the PLAN only"),
    ((NEEDED, None, NEEDED), "review=changes-needed", "RULING: owner/project#3"),
    ((NEEDED, "approved", NEEDED), "review=changes-needed", "RULING: owner/project#3"),
    (("approved", "approved", None), "review=plan-approved", "grade the Execution"),
    (("approved", "approved", "approved"), "review=approved-this-head", TO_REVIEW),
]


class TestSweepAndNext(unittest.TestCase):
    """The sweep's PR line and ``slots next``, from the comments."""

    def test_each_review_has_its_line_and_decision(self) -> None:
        """A rejected plan is revised, a plan approved alone is no approval to merge.

        A review that approves the plan and asks for changes is listed for
        no round, as the ruling is due first (keyword: ruling-first, pitboss#390).
        Only the approval of both is the merge step (the gate's ``act review``).
        """
        for grades, line, decision in OUTPUT_CASES:
            with self.subTest(str(grades)):
                pull_line, decided = outputs(review_comment(*grades))
                assert_that(
                    (line in pull_line, decision in decided), equal_to((True, True))
                )
                merges = TO_REVIEW in decided
                assert_that(merges, equal_to(decision == TO_REVIEW))

    def test_a_plan_approved_alone_is_never_the_merge(self) -> None:
        """Auto-merge is never armed on an approval of the plan alone.

        The control is a review that also grades the execution: that head, not
        clean, is at the merge step all the same.
        """
        armed = []
        for posted in (
            review_comment("approved", "approved", None),
            review_comment("approved", "approved", "approved"),
        ):
            here = quietworld.calm(world_with(posted))
            test_commands.unclean_third(here)
            swept = world.invoke(here, "sweep", here.config, *AFTER).out
            armed.append(TO_REVIEW in decisionline.of(swept, "owner/project#3"))
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

"""Tests for the plan revision round (keyword: plan-revision, pitboss#82)."""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import pulls, reviews, roundlimit, shapes, work
from . import fakes, test_pulls, test_roundlimit, test_work
from .test_commands import sweep
from .test_slot_commands import next_output

APPROVED = reviews.Verdict.APPROVED
CHANGES = reviews.Verdict.CHANGES_NEEDED
HEAD = "3" * 40


def review_comment(
    verdict: str, plan: str | None, execution: str | None, second: int = 1
) -> shapes.Comment:
    """A review comment in the default form with the lines given.

    Args:
        verdict: the verdict word.
        plan: the plan grade, or None for no ``Plan:`` line.
        execution: the execution grade, or None for no ``Execution:`` line.
        second: the second of the minute it was written.

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
    return test_roundlimit.comment("\n".join(lines) + "\n", second)


def line_of_pr3(*posted: shapes.Comment) -> tuple[str, str]:
    """The sweep's line of PR 3 and its line of ``slots next``, or none.

    Args:
        *posted: PR 3's comments.

    Returns:
        The two lines.
    """
    here = test_roundlimit.world_with(posted)
    pull_line = next(
        line for line in sweep(here).out.splitlines() if "owner/project#3 [" in line
    )
    listed = [line for line in next_output(here).splitlines() if "project#3 (" in line]
    return pull_line, "\n".join(listed)


class TestHeadStanding(unittest.TestCase):
    """Where a head stands with a review that grades the plan."""

    def test_standings(self) -> None:
        """A rejected plan, a plan approved alone and the usual cases."""

        def found(
            verdict: reviews.Verdict, plan: reviews.Verdict | None, alone: bool
        ) -> reviews.Standing:
            review = reviews.Found(
                sha=HEAD, verdict=verdict, when="", plan=plan, plan_alone=alone
            )
            return reviews.head_standing(review, HEAD)

        cases = [
            found(CHANGES, CHANGES, False),
            found(CHANGES, CHANGES, True),
            found(CHANGES, APPROVED, False),
            found(CHANGES, None, False),
            found(APPROVED, APPROVED, True),
            found(APPROVED, APPROVED, False),
            found(APPROVED, CHANGES, True),
            found(APPROVED, None, False),
        ]
        plan_rejected = reviews.Standing.PLAN_CHANGES_NEEDED
        changes = reviews.Standing.CHANGES_NEEDED
        expected = [
            plan_rejected,
            plan_rejected,
            changes,
            changes,
            reviews.Standing.PLAN_APPROVED,
            reviews.Standing.APPROVED,
            reviews.Standing.APPROVED,
            reviews.Standing.APPROVED,
        ]
        assert_that(cases, equal_to(expected))


class TestReadingLines(unittest.TestCase):
    """The Plan and Execution lines of a review comment."""

    def test_found_carries_both_lines(self) -> None:
        """A review comment has a plan grade and says whether it grades the plan alone."""
        form = test_roundlimit.FORM
        full = review_comment("approved", "approved", "changes needed").body
        alone = review_comment("approved", "approved", None).body
        bare = review_comment("approved", None, None).body
        found = [
            (roundlimit.plan_grade(body, form), roundlimit.execution_graded(body, form))
            for body in (full, alone, bare)
        ]
        assert_that(
            found, equal_to([(APPROVED, True), (APPROVED, False), (None, False)])
        )

    def test_newest_reads_them(self) -> None:
        """The newest review has the plan grade of its comment; a GitHub review has none."""
        posted = reviews.Sources(
            comments=[review_comment("changes needed", "changes needed", None)],
            reviews=[],
        )
        newest = reviews.newest(posted, test_roundlimit.REVIEW, "owner/project")
        assert_that(
            newest and (newest.plan, newest.plan_alone), equal_to((CHANGES, True))
        )
        github = reviews.Sources(
            comments=[],
            reviews=[
                shapes.PullReview(
                    state="CHANGES_REQUESTED",
                    commit_id=HEAD,
                    author_association="MEMBER",
                    submitted_at="1",
                )
            ],
        )
        newest = reviews.newest(github, test_roundlimit.REVIEW, "owner/project")
        assert_that(
            newest and (newest.plan, newest.plan_alone), equal_to((None, False))
        )


def reviewed(
    number: int, verdict: reviews.Verdict, plan: reviews.Verdict | None, alone: bool
) -> pulls.PullFacts:
    """A green PR whose newest review of its head has the grades given.

    Args:
        number: its number.
        verdict: the review's verdict.
        plan: the review's plan grade.
        alone: whether the review grades the plan alone.

    Returns:
        The PR.
    """
    found = reviews.Found(
        sha=fakes.HEAD, verdict=verdict, when="", plan=plan, plan_alone=alone
    )
    standing = reviews.head_standing(found, fakes.HEAD)
    return dataclasses.replace(
        test_work.facts(number, standing), review=found, standing=standing
    )


class TestKinds(unittest.TestCase):
    """The kind of work a PR is listed as."""

    def test_newest_review_decides_the_kind(self) -> None:
        """Plan changes needed: revise the plan; plan approved: fix the review."""
        settings = fakes.settings(fakes.directory())
        open_pulls = [
            reviewed(1, CHANGES, CHANGES, False),
            reviewed(2, CHANGES, APPROVED, False),
            reviewed(3, CHANGES, None, False),
            reviewed(4, APPROVED, APPROVED, True),
            dataclasses.replace(
                reviewed(5, APPROVED, APPROVED, True),
                pull=test_work.facts(5, reviews.Standing.NONE, draft=True).pull,
            ),
        ]
        found = [
            (each.reference, each.category)
            for each in work.pull_items(open_pulls, settings)
        ]
        kinds = work.Category
        assert_that(
            found,
            equal_to(
                [
                    ("owner/project#1", kinds.REVISE_PLAN),
                    ("owner/project#2", kinds.FIX_REVIEW),
                    ("owner/project#3", kinds.FIX_REVIEW),
                    ("owner/project#4", kinds.REVIEW),
                ]
            ),
        )


class TestSweepAndNext(unittest.TestCase):
    """The sweep's PR line and ``slots next``, from the comments."""

    def test_newest_review_with_plan_changes_needed(self) -> None:
        """Plan changes needed: revise the plan, whatever the execution grade."""
        pull_line, listed = line_of_pr3(
            review_comment("changes needed", "changes needed", "changes needed")
        )
        assert_that(pull_line, contains_string("review=plan-changes-needed"))
        assert_that(listed, contains_string("owner/project#3 (revise the plan,"))

    def test_newest_review_that_says_nothing_of_the_plan(self) -> None:
        """No Plan line and execution changes needed: fix the review."""
        pull_line, listed = line_of_pr3(
            review_comment("changes needed", None, "changes needed")
        )
        assert_that(pull_line, contains_string("review=changes-needed"))
        assert_that(listed, contains_string("owner/project#3 (fix the review,"))

    def test_plan_approved_alone_is_no_approval_to_merge(self) -> None:
        """The execution is reviewed next: the PR is offered for a review, never merged."""
        pull_line, listed = line_of_pr3(review_comment("approved", "approved", None))
        assert_that(pull_line, contains_string("review=plan-approved"))
        assert_that(listed, contains_string("owner/project#3 (review it"))
        here = test_roundlimit.world_with(
            [review_comment("approved", "approved", None)]
        )
        assert_that(
            "READY TO MERGE owner/project#3" in sweep(here).out, equal_to(False)
        )

    def test_plan_approved_with_changes_needed_is_a_ruling_due(self) -> None:
        """The limit still holds the PR: the review that approves the plan counts."""
        posted = review_comment("changes needed", "approved", "changes needed")
        pull_line, listed = line_of_pr3(posted)
        assert_that(pull_line, contains_string("review=changes-needed"))
        assert_that(listed, equal_to(""))

    def test_both_approved_is_ready_to_merge(self) -> None:
        """The control: a review of the plan and the execution that approves merges."""
        here = test_roundlimit.world_with(
            [review_comment("approved", "approved", "approved")]
        )
        swept = sweep(here).out
        assert_that(swept, contains_string("review=approved-this-head"))
        assert_that(swept, contains_string("READY TO MERGE owner/project#3"))


class TestCarryOver(unittest.TestCase):
    """An approval of the plan alone is not carried over merges of the base."""

    def test_older_plan_approval_is_not_an_approval(self) -> None:
        """Only merges since the head it named: the standing is the older head's."""
        for plan_line, expected in [
            ("", reviews.Standing.APPROVED_BEFORE_MERGES),
            ("Plan: approved\n", reviews.Standing.OLDER_HEAD),
        ]:
            found = test_pulls.bodies([test_pulls.AUTHORED, test_pulls.MERGE])
            comment = dict(test_pulls.OLD_GATED_APPROVAL)
            comment["body"] = str(comment["body"]).replace(
                "Verdict:", plan_line + "Verdict:"
            )
            found[fakes.page("repos/owner/project/issues/1/comments")] = [comment]
            project, _ = test_pulls.read(found)
            assert_that(project.standing, equal_to(expected))

"""Tests for the sweep's PR line."""

import json
import unittest

from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, parsing, pulls, report, reviews, shapes, steps
from . import fakes


def run(finished: bool) -> shapes.CheckRun:
    """A check run that did not fail.

    Args:
        finished: whether it completed.

    Returns:
        The check run.
    """
    return shapes.CheckRun(id=1, name="check", finished=finished, failed=False)


def facts(
    standing: reviews.Standing,
    found: reviews.Found | None = None,
    unread: str = "",
    checks: Sequence[shapes.CheckRun] = (),
    **changes: object,
) -> pulls.PullFacts:
    """A PR with a review standing.

    Args:
        standing: where its head stands.
        found: its newest review.
        unread: when a comment not in the form was written.
        checks: its head's check runs.
        **changes: fields of the PR's JSON to replace.

    Returns:
        The PR.
    """
    repo = config.Repo(owner="o", name="r", slug="o/r")
    pull = parsing.pull(json.dumps(fakes.pull_body(7, **changes)))
    return pulls.PullFacts(
        repo=repo,
        pull=pull,
        checks=checks,
        review=found,
        standing=standing,
        unread=unread,
        step=steps.wait_for_ci(),
    )


class TestPullLine(unittest.TestCase):
    """The review part of a PR's line."""

    def test_unread_comment_is_said(self) -> None:
        """A newer comment that is not in the form is named on the line."""
        line = report.pull_line(
            facts(reviews.Standing.CHANGES_NEEDED, unread="04:27"), {}
        )
        assert_that(line, contains_string("review=changes-needed (ignored: the"))
        assert_that(line, contains_string("comment of 04:27 is not in the review"))

    def test_nothing_unread_adds_nothing(self) -> None:
        """Without one, the line ends as it did."""
        line = report.pull_line(facts(reviews.Standing.CHANGES_NEEDED), {})
        assert_that("ignored" in line, equal_to(False))


def lines(pull: pulls.PullFacts) -> str:
    """The action lines of a PR, as one text.

    Args:
        pull: the PR.

    Returns:
        The lines, joined.
    """
    settings = fakes.settings(fakes.directory())
    return "\n".join(report.action_lines(pull, settings, False, {}))


class TestWaitForCi(unittest.TestCase):
    """A head with no completed check run waits for CI and is never ready."""

    def test_a_head_with_no_completed_check_run_waits(self) -> None:
        """No run, a run in progress, and a draft with no run all wait."""
        approved = reviews.Standing.APPROVED
        cases = {
            "no check runs": facts(approved),
            "check run in progress": facts(approved, checks=[run(False)]),
            "draft": facts(approved, draft=True),
        }
        for name, pull in cases.items():
            with self.subTest(name):
                assert_that(lines(pull), contains_string("WAIT-FOR-CI o/r#7"))
                assert_that("READY" in lines(pull), equal_to(False))
                assert_that(pulls.green(pull), equal_to(False))

    def test_completed_check_run_is_ready(self) -> None:
        """A completed green check run ends the wait and the PR is ready."""
        pull = facts(reviews.Standing.APPROVED, checks=[run(True)])
        assert_that("WAIT-FOR-CI" in lines(pull), equal_to(False))
        assert_that(lines(pull), contains_string("READY TO MERGE o/r#7"))


class TestAutoMergeOff(unittest.TestCase):
    """``AUTO MERGE OFF`` is for a head whose newest review approved it (#85)."""

    def test_only_an_approved_head_is_told_to_arm_again(self) -> None:
        """No review and an older head's review print no line; approval does."""
        for standing, printed in [
            (reviews.Standing.NONE, False),
            (reviews.Standing.OLDER_HEAD, False),
            (reviews.Standing.APPROVED_BEFORE_MERGES, False),
            (reviews.Standing.CHANGES_NEEDED, False),
            (reviews.Standing.PLAN_CHANGES_NEEDED, False),
            (reviews.Standing.PLAN_APPROVED, False),
            (reviews.Standing.APPROVED, True),
        ]:
            with self.subTest(standing.name):
                pull = facts(standing, checks=[run(True)], mergeable_state="has_hooks")
                assert_that("AUTO MERGE OFF" in lines(pull), equal_to(printed))

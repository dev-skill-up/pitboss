"""Tests for the sweep's PR line."""

import dataclasses
import json
import unittest

from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, parsing, pulls, report, reviews, shapes, steps, straycomments
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
        unreadable=straycomments.StrayComments(newer=unread),
        step=steps.ci_pending(),
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


def approved_green() -> pulls.PullFacts:
    """An approved PR whose check run passed.

    Returns:
        The PR.
    """
    return facts(reviews.Standing.APPROVED, checks=[run(True)])


class TestWaitForCi(unittest.TestCase):
    """A head is green only when every check run completed and none failed."""

    def test_a_head_with_no_completed_check_run_is_not_green(self) -> None:
        """No run, a run in progress, and a draft with no run are not green."""
        approved = reviews.Standing.APPROVED
        cases = {
            "no check runs": facts(approved),
            "check run in progress": facts(approved, checks=[run(False)]),
            "draft": facts(approved, draft=True),
        }
        for name, pull in cases.items():
            with self.subTest(name):
                assert_that(pulls.green(pull), equal_to(False))

    def test_completed_check_run_is_ready(self) -> None:
        """A completed check run that did not fail makes the head green."""
        assert_that(pulls.green(approved_green()), equal_to(True))


def at_merge(pull: pulls.PullFacts) -> pulls.PullFacts:
    """A PR at the MERGE step.

    Args:
        pull: the PR.

    Returns:
        The PR.
    """
    return dataclasses.replace(pull, step=steps.merge())


def by_hand(pull: pulls.PullFacts) -> pulls.PullFacts:
    """A PR of a library without auto-merge, at the MERGE step.

    Args:
        pull: the PR.

    Returns:
        The PR.
    """
    repo = config.Repo(owner="owner", name="lib", slug="owner/lib")
    return dataclasses.replace(pull, step=steps.merge(), repo=repo)


NO_AUTO_MERGE_LIB = '[libraries]\nrepositories = ["lib"]\nno_auto_merge = ["lib"]\n'


def by_hand_settings() -> config.Config:
    """A configuration whose library ``lib`` has no auto-merge.

    Returns:
        The configuration.
    """
    return fakes.settings(fakes.directory(), NO_AUTO_MERGE_LIB)

"""Tests for the sweep's PR line."""

import json
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import config, parsing, pulls, report, reviews
from . import fakes


def facts(
    standing: reviews.Standing, found: reviews.Found | None = None, unread: str = ""
) -> pulls.PullFacts:
    """A PR with a review standing.

    Args:
        standing: where its head stands.
        found: its newest review.
        unread: when a comment not in the form was written.

    Returns:
        The PR.
    """
    repo = config.Repo(owner="o", name="r", slug="o/r")
    pull = parsing.pull(json.dumps(fakes.pull_body(7)))
    return pulls.PullFacts(
        repo=repo,
        pull=pull,
        checks=(),
        review=found,
        standing=standing,
        unread=unread,
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

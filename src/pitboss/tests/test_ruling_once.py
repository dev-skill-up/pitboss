"""A6: ``pitboss ruling post`` refuses a second ruling before the PR is paused.

Owner, 2026-11-11: one ruling per PR; a further rejection goes to the owner
(pitboss#444, keyword: one-ruling).
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import rulingguard
from . import fakes, world
from .test_ruling_post import COMMENTS, GOOD, PULL, URL

LISTED = fakes.page(f"{world.PROJECT}/issues/3/comments")
ISSUE = f"{world.PROJECT}/issues/3"
EARLIER = {"id": 1, "html_url": "u", "body": GOOD}
REVIEW = {"id": 2, "html_url": "u", "body": "Review\nVerdict: changes needed\n"}


def post(
    comments: Sequence[object], labels: Sequence[str]
) -> tuple[str, Sequence[str]]:
    """Run ``ruling post`` on PR 3 with some comments and labels.

    Args:
        comments: the comments the PR has.
        labels: the PR's labels.

    Returns:
        What the command printed on standard error, and the texts it posted.
    """
    here = world.make_world()
    here.bodies[COMMENTS] = {"id": 5, "html_url": URL}
    here.bodies[LISTED] = list(comments)
    here.bodies[ISSUE] = {"labels": [{"name": each} for each in labels]}
    path = here.workspace / "ruling.md"
    path.write_text(GOOD, encoding="utf-8")
    done = world.invoke(here, "ruling", "post", PULL, str(path))
    sent = [each for each in here.calls if each[-1].endswith("issues/3/comments")]
    return done.err, [each[each.index("-f") + 1] for each in sent if "-f" in each]


class TestOnce(unittest.TestCase):
    """A PR gets one ruling; the owner decides after it."""

    def test_a6_a_second_ruling_before_the_pause_is_refused(self) -> None:
        """Pitboss 465: a ruling, a rejection, and a second ruling is posted."""
        err, sent = post([EARLIER, REVIEW], [])
        assert_that(err, contains_string("already has an Opus ruling"))
        assert_that(sent, empty())

    def test_a6_the_first_ruling_is_posted(self) -> None:
        """The nearest input it must still accept: no ruling yet."""
        err, sent = post([REVIEW], [])
        assert_that((err, len(sent)), equal_to(("", 1)))

    def test_a6_a_paused_pr_takes_a_ruling_again(self) -> None:
        """The owner decided; the label says the PR is paused."""
        err, sent = post([EARLIER], ["paused-owner"])
        assert_that((err, len(sent)), equal_to(("", 1)))

    def test_a6_the_guard_reads_the_first_line_of_a_comment(self) -> None:
        """A comment that only mentions a ruling is no ruling."""
        said = ["Review: the Opus ruling is wrong"]
        assert_that(rulingguard.refusal(said, []), equal_to(""))

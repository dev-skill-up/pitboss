"""A6: ``pitboss ruling post`` refuses a second ruling before the PR is paused.

Owner, 2026-11-11: one ruling per PR; a further rejection goes to the owner
(pitboss#444, keyword: one-ruling).
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import rulingguard
from . import fakes, refused, world
from .test_ruling_post import COMMENTS, GOOD, PULL, URL

ISSUE = f"{world.PROJECT}/issues/3"
LISTED = fakes.page(f"{ISSUE}/comments")
EARLIER = {"id": 1, "html_url": "u", "body": GOOD}
REVIEW = {"id": 2, "html_url": "u", "body": "Review\nVerdict: changes needed\n"}


def world_with(comments: Sequence[object], labels: Sequence[str]) -> world.World:
    """A world whose PR 3 has some comments and labels and takes a comment.

    Args:
        comments: the comments the PR has.
        labels: the PR's labels.

    Returns:
        The world.
    """
    labelled = [{"name": each} for each in labels]
    return refused.world_of(
        {
            COMMENTS: {"id": 5, "html_url": URL},
            LISTED: list(comments),
            ISSUE: {"labels": labelled},
        }
    )


def posted(here: world.World) -> Sequence[str]:
    """Run ``ruling post`` on PR 3 and give the rulings it posted.

    Args:
        here: the world.

    Returns:
        The texts posted.
    """
    refused.run(here, GOOD, "ruling", "post", PULL, refused.FILE)
    return refused.bodies(here)


class TestOnce(unittest.TestCase):
    """A PR gets one ruling; the owner decides after it."""

    def test_a6_a_second_ruling_before_the_pause_is_refused(self) -> None:
        """Pitboss 465: a ruling, a rejection, and a second ruling is posted."""
        here = world_with([EARLIER, REVIEW], [])
        done = refused.run(here, GOOD, "ruling", "post", PULL, refused.FILE)
        refused.assert_refused(done, "already has an Opus ruling", here)

    def test_a6_the_first_ruling_is_posted(self) -> None:
        """The nearest input it must still accept: no ruling yet."""
        assert_that(posted(world_with([REVIEW], [])), equal_to([GOOD]))

    def test_a6_a_paused_pr_takes_a_ruling_again(self) -> None:
        """The owner decided; the label says the PR is paused."""
        assert_that(posted(world_with([EARLIER], ["paused-owner"])), equal_to([GOOD]))

    def test_a6_the_guard_reads_the_first_line_of_a_comment(self) -> None:
        """A comment that only mentions a ruling is no ruling."""
        said = ["Review: the Opus ruling is wrong"]
        assert_that(rulingguard.refusal(said, []), equal_to(""))

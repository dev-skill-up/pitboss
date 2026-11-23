"""The PR a verb changes is the one its decision carries (keyword: accepts)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import actport, actverbs, gateverbs
from .knownkit import NUMBER, REPO, made
from .knownshipped import GIVEN

BRANCH = "claude/project-thread-y4iyll"  # the branch of the PR the kit holds
PULL = f"{REPO}#{NUMBER}"


def bound(verb: str, number: int, options: Mapping[str, str]) -> str:
    """The PR a verb of the kit's world is about.

    Args:
        verb: the verb's word.
        number: its target's number.
        options: its options.

    Returns:
        ``actverbs.item_of``.
    """
    asked = actport.Asked(
        verb=verb, target=actport.Target(repo=REPO, number=number), options=options
    )
    return actverbs.item_of(made(GIVEN).act, gateverbs.verb_of(verb), asked)


class TestBound(unittest.TestCase):
    """Which PR a verb is about, empty when it is about none."""

    def test_a_review_is_about_its_target(self) -> None:
        """The review needs no lookup."""
        assert_that(bound("review", 7, {}), equal_to(f"{REPO}#7"))

    def test_a_push_and_a_dispatch_are_about_the_pr_of_the_branch(self) -> None:
        """The branch names the PR; a branch no open PR has is about none."""
        said = [
            bound("push", 0, {"branch": BRANCH}),
            bound("dispatch-workflow", 0, {"ref": BRANCH}),
            bound("push", 0, {"branch": "first-round"}),
        ]
        assert_that(said, equal_to([PULL, PULL, ""]))

    def test_a_close_is_about_a_pr_not_an_issue(self) -> None:
        """The number names an open PR, or an issue that is none."""
        said = [bound("close", NUMBER, {}), bound("close", 5, {})]
        assert_that(said, equal_to([PULL, ""]))

    def test_only_a_foreign_label_is_a_step(self) -> None:
        """The owner's, priority and hold labels are settings, not steps (T133)."""
        said = [
            bound("label", NUMBER, {"name": each})
            for each in ("dependencies", "paused-owner", "p1")
        ]
        assert_that(said, equal_to([PULL, "", ""]))

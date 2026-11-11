"""A ruling's steps done in the body alone, and ``slots next --step`` (pitboss#462).

GitHub gives no time for a body edit, so the clean ``Plan check`` newer than the
ruling is the record of the round (keyword: body-only-round).
"""

import dataclasses
import unittest

from hamcrest import assert_that, equal_to

from .. import flow, flowstate, plancheckflow, shapes, steps
from . import test_flow, test_flow_sweep as scenes, world
from .checkcomment import clean_text
from .itemworld import one, with_pull_issues
from .says import says
from .test_flow import expect, state
from .worldcomments import CLEAN_CHECK

OK = "Plan check: ok"
REVIEW = steps.regular_review(steps.Stage.RULING_STEPS)
FIX = steps.worker(steps.Task.RULING_STEPS, "https://example.org/ruling/3")
REJECTIONS = (test_flow.FIRST_REJECTION, test_flow.SECOND_REJECTION)
RULE = "--step review prints the brief of a PR only when its step is a review"


def check_after(text: str, digest: str = "") -> shapes.Comment:
    """A ``Plan check`` of the Plan, written after the ruling.

    Args:
        text: the last line of the check.
        digest: the Plan digest line it records, that of the body's Plan when "".

    Returns:
        The comment.
    """
    clean = clean_text(test_flow.BODY).replace(OK, text)
    body = clean.replace(clean.splitlines()[1], digest or clean.splitlines()[1])
    return shapes.Comment(
        body=body,
        author_association="MEMBER",
        created_at="2026-10-30T00:00:04Z",
        url="https://example.org/check/4",
    )


def ruled(*after: shapes.Comment) -> flow.PullState:
    """A PR ruled ``do these steps`` after two Plan rejections.

    Args:
        *after: the comments after the ruling.

    Returns:
        The state.
    """
    return state(*REJECTIONS, comments=[test_flow.ruling(3), *after])


class TestBodyOnlyRound(unittest.TestCase):
    """The step of a ruling whose steps the body alone could do."""

    def test_a_clean_check_after_the_ruling_gives_the_review(self) -> None:
        """The body was fixed and checked: the review of the ruling's steps."""
        expect(REVIEW, ruled(check_after(OK)))

    def test_no_check_after_the_ruling_gives_the_fix(self) -> None:
        """The body was not edited after the ruling."""
        expect(FIX, ruled())

    def test_a_refusal_after_the_ruling_gives_the_fix(self) -> None:
        """The newest check of the Plan refuses it."""
        expect(FIX, ruled(check_after("Plan check: refused, rows: 1")))

    def test_a_clean_check_of_another_plan_gives_the_fix(self) -> None:
        """The check names a Plan that is not the one now."""
        expect(FIX, ruled(check_after(OK, f"Plan digest: {'0' * 16}")))

    def test_a_clean_check_before_the_ruling_is_not_since(self) -> None:
        """The nearest input checked_since must still reject: a check that is older."""
        older = dataclasses.replace(check_after(OK), created_at="2026-10-30T00:00:01Z")
        for comments, want in [([older], False), ([check_after(OK)], True)]:
            with self.subTest(len(comments)):
                pr = ruled(*comments)
                found = plancheckflow.checked_since(pr, flowstate.readable_comment)
                assert_that(found, equal_to(want))

    def test_unchecked_and_review_follow_the_check(self) -> None:
        """A refused Plan is unchecked, and its review is the fix round."""
        refused = ruled(check_after("Plan check: refused, rows: 1"))
        assert_that(plancheckflow.unchecked(refused), equal_to(True))
        assert_that(plancheckflow.unchecked(ruled(check_after(OK))), equal_to(False))
        assert_that(
            plancheckflow.review(ruled(check_after(OK)), steps.Stage.PLAN_ONLY),
            equal_to(steps.regular_review(steps.Stage.PLAN_ONLY)),
        )
        again = plancheckflow.review(refused, steps.Stage.PLAN_ONLY)
        assert_that(again.step, equal_to(steps.Step.SEND_BACK_PLAN_CHECK))

    def test_plan_unrun_needs_a_review_after_the_ruling(self) -> None:
        """With no review that counts, no round is offered."""
        found = plancheckflow.plan_unrun(ruled(), None, flowstate.readable_comment)
        assert_that(found, equal_to(None))


def ruled_world(word: str, *after: shapes.Comment) -> world.World:
    """PR 3 ruled after two Plan rejections.

    Args:
        word: what the ruling rules.
        *after: the comments after the ruling.

    Returns:
        The world, with the issues of its PRs.
    """
    rounds = [*scenes.TWO_PLAN_REJECTIONS, scenes.ruled_by(f"Ruling: {word}")]
    return with_pull_issues(scenes.world_with([*rounds, *after]))


def refused(here: world.World, reference: str, *words: str) -> None:
    """Require the refusal of the step: status 1, nothing printed, words said.

    Args:
        here: the world.
        reference: the item.
        *words: what standard error says.
    """
    found = one(here, reference, "--step", "review")
    says(found.err, "UNKNOWN", f"{reference} is not at the review step", RULE, *words)
    assert_that((found.out, found.code), equal_to(("", 1)))


class TestStepReview(unittest.TestCase):
    """``slots next --step review`` prints a review brief or refuses."""

    def test_a_pr_at_the_review_is_briefed(self) -> None:
        """The body round is done: the review brief, status 0."""
        newer = shapes.Comment(
            body=CLEAN_CHECK["body"],
            author_association="MEMBER",
            created_at="2026-10-30T00:00:05Z",
        )
        found = one(
            ruled_world("do these steps", newer), "owner/project#3", "--step", "review"
        )
        assert_that("UNKNOWN" in found.err, equal_to(False))
        says(found.out, "owner/project#3", "review")

    def test_a_pr_at_a_fix_is_refused_with_its_step_and_the_rule(self) -> None:
        """Exit 1, UNKNOWN, the actual step and the rule on standard error."""
        refused(
            ruled_world("do these steps"),
            "owner/project#3",
            "do the steps of the Opus ruling",
        )

    def test_a_pr_at_another_step_is_refused(self) -> None:
        """A ruling to split is carried out, not reviewed."""
        refused(ruled_world("split"), "owner/project#3", "carry out the Opus ruling")

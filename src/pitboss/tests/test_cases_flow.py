"""I15, I24, I32 and I38: the step after a ruling, and a fix round that waits.

Cases 15, 24, 32 and 38 of pitboss#444 (keywords: ruling-since, fix-round-waiting).
The flow tests plant the timeline of the case on the model of a PR; the sweep
test plants a fix round with no reviewer.
"""

import dataclasses
import datetime
import unittest
from typing import Any

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import fixwait, pulls, reviews, rulingreason, shapes, steps
from . import model
from .model import History, Model, Ruling, Verdict
from .test_work import REPO, facts

V = Verdict
APPROVED_PLAN = [(3, V.APPROVED, None, 0, 0)]
RULED = [(4, Ruling.DO_THESE_STEPS)]


def step_of(made: Model) -> steps.Next:
    """The step the flow gives a PR.

    Args:
        made: the PR.

    Returns:
        The step.
    """
    return model.step_of(made)


class TestAfterTheRuling(unittest.TestCase):
    """The ruling's steps, then the review that follows them."""

    def test_i24_a_plan_check_before_the_ruling_still_asks_for_its_steps(self) -> None:
        """Ruling `do these steps` newer than the Plan check: the worker's round."""
        made = Model(history=History(reviews=APPROVED_PLAN, rulings=RULED))
        got = step_of(made)
        assert_that(
            (got.step, got.task), equal_to((steps.Step.WORKER, steps.Task.RULING_STEPS))
        )

    def test_i24_a_plan_check_after_the_ruling_at_the_head_is_the_review(self) -> None:
        """PR 460 at 04:41Z: the steps were done, the review is the step."""
        history = History(reviews=APPROVED_PLAN, rulings=RULED, checks=[(2, 0), (5, 0)])
        got = step_of(Model(history=history))
        assert_that(got.step, equal_to(steps.Step.REGULAR_REVIEW))
        assert_that(got.stage, equal_to(steps.Stage.RULING_STEPS))

    def test_i32_a_plan_check_newer_than_the_ruling_is_reviewed(self) -> None:
        """A Plan not yet reviewed after the ruling and a newer check: a review."""
        history = History(rulings=RULED, checks=[(2, 0), (5, 0)])
        got = step_of(Model(history=history))
        assert_that(got.step, equal_to(steps.Step.REGULAR_REVIEW))

    def test_i15_a_revised_plan_after_the_ruling_is_reviewed_not_rewritten(
        self,
    ) -> None:
        """`revise the plan` done at a new head with a clean check: the review."""
        history = History(
            reviews=APPROVED_PLAN,
            rulings=[(4, Ruling.REVISE_THE_PLAN)],
            checks=[(2, 0), (5, 1)],
        )
        got = step_of(Model(plan=1, head=1, pushed=6, history=history))
        assert_that(got.step, equal_to(steps.Step.REGULAR_REVIEW))
        assert_that(got.task, equal_to(None))


NOW = datetime.datetime(2026, 11, 12, 12, 0, tzinfo=datetime.timezone.utc)
FINDINGS = "https://github.example/owner/project/pull/5#c1"


def fix_round(started: str, **more: Any) -> pulls.PullFacts:
    """A PR whose newest review asked for changes and whose head moved since.

    Args:
        started: when its head's check started.
        **more: changes to the PR's facts.

    Returns:
        The facts.
    """
    seen = facts(5, reviews.Standing.OLDER_HEAD)
    check = shapes.CheckRun(
        id=1, name="build", finished=True, failed=False, started_at=started
    )
    found = reviews.Found(
        sha="a" * 7, verdict=reviews.Verdict.CHANGES_NEEDED, when="t", url=FINDINGS
    )
    return dataclasses.replace(seen, checks=(check,), review=found, **more)


class TestFixRoundWaiting(unittest.TestCase):
    """I38: a fix round without a reviewer is named after thirty minutes."""

    def test_i38_a_wait_over_thirty_minutes_is_named_with_the_findings(self) -> None:
        """The minutes, the PR, the head and the findings' address."""
        got = fixwait.lines([fix_round("2026-11-12T11:00:00Z")], NOW, set())
        assert_that(got, has_length(1))
        assert_that(
            got[0], contains_string("FIX ROUND WAITING 60 minutes: owner/project#5")
        )
        assert_that(got[0], contains_string(FINDINGS))

    def test_i38_a_recent_round_or_one_with_an_agent_is_not_named(self) -> None:
        """Under thirty minutes, an agent on it, or no check yet: nothing."""
        recent = fix_round("2026-11-12T11:45:00Z")
        old = fix_round("2026-11-12T11:00:00Z")
        assert_that(fixwait.lines([recent], NOW, set()), equal_to([]))
        assert_that(fixwait.lines([old], NOW, {"owner/project#5"}), equal_to([]))
        assert_that(fixwait.lines([fix_round("")], NOW, set()), equal_to([]))

    def test_i38_the_longest_wait_comes_first_and_a_plain_review_is_not_named(
        self,
    ) -> None:
        """Two rounds in order of the wait; an ordinary review is no fix round."""
        longer = fix_round("2026-11-12T08:00:00Z")
        shorter = dataclasses.replace(
            fix_round("2026-11-12T11:00:00Z"),
            pull=facts(6, reviews.Standing.OLDER_HEAD).pull,
        )
        plain = facts(7, reviews.Standing.NONE)
        got = fixwait.lines([shorter, longer, plain], NOW, set())
        assert_that(
            [each.split(":")[0] for each in got],
            equal_to(["FIX ROUND WAITING 240 minutes", "FIX ROUND WAITING 60 minutes"]),
        )
        assert_that(REPO.slug, equal_to("owner/project"))


RULING_TEXT = "Opus ruling\nRuling: do these steps\n"
CHECK_TEXT = "Plan check\nrow 1: ran\nPlan check: ok\n"


def _comment(body: str, at: str) -> shapes.Comment:
    return shapes.Comment(body=body, author_association="MEMBER", created_at=at)


class TestRulingReason(unittest.TestCase):
    """I24: the line says the two comment times that decided the review."""

    def test_i24_the_review_line_names_the_ruling_and_the_plan_check_times(
        self,
    ) -> None:
        """A ruling at 04:26Z and a Plan check at 04:41Z: both times are said."""
        comments = [
            _comment(RULING_TEXT, "2026-11-11T04:26:00Z"),
            _comment(CHECK_TEXT, "2026-11-11T04:41:11Z"),
        ]
        review = steps.regular_review(steps.Stage.RULING_STEPS)
        times = rulingreason.times(comments, frozenset({"MEMBER"}), review)
        said = rulingreason.reason(times)
        assert_that(said, contains_string("2026-11-11T04:41:11Z is later"))
        assert_that(said, contains_string("ruling of 2026-11-11T04:26:00Z"))

    def test_i24_another_step_or_a_missing_comment_says_nothing(self) -> None:
        """The nearest input that must stay silent."""
        comments = [_comment(RULING_TEXT, "2026-11-11T04:26:00Z")]
        trusted = frozenset({"MEMBER"})
        other = rulingreason.times(comments, trusted, steps.merge())
        review = steps.regular_review(steps.Stage.RULING_STEPS)
        lone = rulingreason.times(comments, trusted, review)
        assert_that(
            (rulingreason.reason(other), rulingreason.reason(lone)), equal_to(("", ""))
        )

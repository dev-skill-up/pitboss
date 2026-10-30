"""Tests for what follows an Opus ruling (keyword: review-flow, pitboss#107)."""

import unittest

from hamcrest import assert_that, equal_to

from .. import rulings, steps
from .test_flow import GREEN, RED, RUNNING, ruling, state
from .test_flow import PLAN_REJECTED, graded

Task = steps.Task
Stage = steps.Stage
WORDS = [
    ("do these steps\n1. x", rulings.Ruling.DO_THESE_STEPS),
    ("revise the plan", rulings.Ruling.REVISE_THE_PLAN),
    ("execution is approved", rulings.Ruling.EXECUTION_IS_APPROVED),
    ("split", rulings.Ruling.SPLIT),
    ("reshape", rulings.Ruling.RESHAPE),
    ("abandon", rulings.Ruling.ABANDON),
    ("escalate to the owner", rulings.Ruling.ESCALATE),
    ("whatever", None),
]


def read(text: str) -> rulings.Ruling | None:
    """Read a ruling comment whose second line is ``Ruling: `` and a word.

    Args:
        text: the second line's word, and what follows.

    Returns:
        The ruling.
    """
    return rulings.read_ruling(f"Opus ruling\nRuling: {text}")


class TestReading(unittest.TestCase):
    """A ruling is read from its second line."""

    def test_each_word_names_a_ruling(self) -> None:
        """``Ruling: <word>`` names it; an unknown word names none."""
        found = [read(text) for text, _ in WORDS]
        assert_that(found, equal_to([ruled for _, ruled in WORDS]))

    def test_anything_else_names_none(self) -> None:
        """Not a ruling, no second line, or a second line that is no ruling."""
        bodies = ["Ruling: split", "Opus ruling", "Opus ruling\nno ruling line"]
        found = [rulings.read_ruling(body) for body in bodies]
        assert_that(found, equal_to([None, None, None]))


class TestAfter(unittest.TestCase):
    """The steps that follow each ruling."""

    def test_do_these_steps_then_a_review_of_the_steps(self) -> None:
        """A worker does exactly the steps; a regular review checks only them."""
        found = rulings.after_opus_ruling(state(), rulings.Ruling.DO_THESE_STEPS)
        expected = (
            steps.worker(Task.RULING_STEPS),
            steps.regular_review(Stage.RULING_STEPS),
        )
        assert_that(found, equal_to(expected))

    def test_revise_the_plan_then_a_review_of_the_plan(self) -> None:
        """The plan only, then a review of the plan."""
        found = rulings.after_opus_ruling(state(), rulings.Ruling.REVISE_THE_PLAN)
        expected = (
            steps.worker(Task.REVISE_PLAN),
            steps.regular_review(Stage.PLAN_ONLY),
        )
        assert_that(found, equal_to(expected))

    def test_an_approved_execution_merges_when_the_checks_are_green(self) -> None:
        """Otherwise the CI gate says what to do."""
        approved = rulings.Ruling.EXECUTION_IS_APPROVED
        found = [
            rulings.after_opus_ruling(state(checks=checks), approved)
            for checks in ((GREEN,), (RUNNING,), (RED,))
        ]
        expected = [
            (steps.merge(),),
            (steps.wait_for_ci(),),
            (steps.worker(Task.FIX_CI),),
        ]
        assert_that(found, equal_to(expected))

    def test_split_reshape_and_abandon_are_carried_out_as_ruled(self) -> None:
        """No check against the one-ticket-one-PR rules, whatever the PR is."""
        any_state = [
            state(),
            state(draft=True, body=""),
            state(graded(*PLAN_REJECTED, 1), comments=[ruling(2)], checks=(RED,)),
        ]
        ruled = (rulings.Ruling.SPLIT, rulings.Ruling.RESHAPE, rulings.Ruling.ABANDON)
        found = {
            rulings.after_opus_ruling(pr, each) for pr in any_state for each in ruled
        }
        assert_that(found, equal_to({(steps.worker(Task.RULING_AS_GIVEN),)}))

    def test_escalating_pauses_for_the_owner(self) -> None:
        """The owner is told."""
        found = rulings.after_opus_ruling(state(), rulings.Ruling.ESCALATE)
        assert_that(found, equal_to((steps.pause_for_owner(),)))


class TestDescribe(unittest.TestCase):
    """Every step says what to do."""

    def test_every_step_says_what_to_do(self) -> None:
        """One line of text for each step, with its task or stage."""
        every = [
            steps.worker(Task.REVISE_PLAN),
            steps.regular_review(Stage.PLAN_ONLY),
            *(steps.Next(step=each) for each in steps.TEXTS),
        ]
        found = [steps.describe(each) for each in every]
        assert_that(all(text and "\n" not in text for text in found), equal_to(True))
        assert_that(len(set(found)), equal_to(len(every)))

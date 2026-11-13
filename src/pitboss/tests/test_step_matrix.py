"""Every step and task has a printed next step (keyword: step-matrix, quire#1115).

An edited approved Plan was refused with no ruling brief and `slots next` printed
nothing for the PR, so the queue wrote the brief by hand. The matrix is derived from
the enums and from what the code prints for each member; a member with no row, a
step whose text asks for a ruling but offers no brief, and a printed channel that
is missing each fail (and a planted one of each is shown to fail).
"""

import dataclasses
import enum
import unittest
from typing import AbstractSet, Mapping

from hamcrest import assert_that, empty, equal_to, has_item

from .. import (
    stepwords,
    configfile,
    phrases,
    pulllines,
    reviews,
    stepmatrix,
    steps,
    work,
)
from . import test_work, world

QUIET = ("state", "next")
ROWS = stepmatrix.parse(phrases.shipped_text("stepmatrix.tsv"))
BASE = test_work.facts(3, reviews.Standing.NONE)


def steps_of() -> Mapping[str, steps.Next]:
    """A step for each member, as the flow would give it.

    Returns:
        The steps by member name; a task is the worker step of it.
    """
    given = {
        f"Step.{each.name}": steps.Next(step=each, comment="c", findings="f")
        for each in steps.Step
    }
    given["Step.WORKER"] = steps.worker(steps.Task.FIRST_ROUND)
    given["Step.REGULAR_REVIEW"] = steps.regular_review(steps.Stage.PLAN_ONLY)
    return {
        **given,
        **{f"Task.{each.name}": steps.worker(each) for each in steps.Task},
    }


def printed(name: str, rulings: AbstractSet[steps.Step] = stepmatrix.RULINGS) -> str:
    """The channels a step is printed in, from the code.

    Args:
        name: the member.
        rulings: the steps that are offered a ruling brief.

    Returns:
        ``brief`` for a ruling brief, ``category`` for a briefed round, ``line`` for
        a sweep line, else ``state``.
    """
    step = steps_of()[name]
    pull = dataclasses.replace(BASE, step=step)
    settings = configfile.load(name=_world().config, start=_world().workspace)
    if step.step in rulings:
        return "brief"
    if work.category_of(pull) is not None:
        return "category"
    if pulllines.lines(pull, world.START, settings, ({}, {})):
        return "line"
    return "state"


def _world() -> world.World:
    return world.make_world()


class MoreSteps(enum.Enum):
    """A step enum with one member the file has no row for.

    Attributes:
        BRAND_NEW: the member with no row.
    """

    BRAND_NEW = 1


class TestTheMatrix(unittest.TestCase):
    """The rows against the enums and the code."""

    def test_every_member_has_a_row_and_every_row_a_member(self) -> None:
        """Both directions, derived from the enums."""
        texts = {each: stepwords.describe(step) for each, step in steps_of().items()}
        assert_that(stepmatrix.findings(ROWS, stepmatrix.members(), texts), empty())

    def test_a_new_member_without_a_row_is_found(self) -> None:
        """Planted: an enum with one more member, and a row of a gone member."""
        found = stepmatrix.findings(ROWS, stepmatrix.members(MoreSteps), {})
        assert_that(found, has_item("Step.BRAND_NEW has no row in stepmatrix.tsv"))
        gone = {**ROWS, "Step.GONE": ("state", "x")}
        found = stepmatrix.findings(gone, stepmatrix.members(), {})
        assert_that(found, has_item("Step.GONE is no member of steps"))

    def test_every_step_has_text_and_none_says_unknown(self) -> None:
        """The PR STATE line of every member is a sentence, never UNKNOWN or empty."""
        for name, step in steps_of().items():
            with self.subTest(name):
                assert_that(stepwords.describe(step).strip() != "", equal_to(True))
                assert_that("UNKNOWN" in stepwords.describe(step), equal_to(False))

    def test_every_step_is_printed_in_the_channel_its_row_names(self) -> None:
        """The code prints what the row needs: a brief, a briefed round or a line."""
        for name, (need, _) in ROWS.items():
            if need in QUIET:
                continue
            with self.subTest(name):
                assert_that(printed(name), equal_to(need))

    def test_a_plan_edited_pr_is_offered_a_ruling_brief_quire_1115(self) -> None:
        """The state of quire#1115: without the brief the row is not met."""
        assert_that(printed("Step.PLAN_EDITED"), equal_to("brief"))
        without = stepmatrix.RULINGS - {steps.Step.PLAN_EDITED}
        assert_that(printed("Step.PLAN_EDITED", without), equal_to("line"))

    def test_a_step_that_asks_for_a_ruling_must_be_a_brief_row(self) -> None:
        """Planted: PLAN_EDITED as a line row is found by its own text."""
        texts = {"Step.PLAN_EDITED": stepwords.describe(steps.plan_edited())}
        weak = {**ROWS, "Step.PLAN_EDITED": ("line", "")}
        found = stepmatrix.findings(weak, stepmatrix.members(), texts)
        asked = [each for each in found if each.endswith("so it needs a brief")]
        assert_that(len(asked), equal_to(1))

    def test_an_unknown_need_and_a_state_row_with_no_reason_are_found(self) -> None:
        """Planted: a need the file does not know, and a state row without why."""
        odd = {**ROWS, "Step.WAIT": ("sometimes", ""), "Step.MERGE": ("state", "")}
        found = stepmatrix.findings(odd, stepmatrix.members(), {})
        assert_that(found, has_item("Step.WAIT: unknown need 'sometimes'"))
        assert_that(found, has_item("Step.MERGE: a state row names its reason"))

    def test_a_state_row_prints_the_state_alone(self) -> None:
        """No brief, round or line: the PR STATE text is all there is."""
        alone = [name for name, (need, _) in ROWS.items() if need == "state"]
        assert_that(len(alone) > 0, equal_to(True))
        for name in alone:
            with self.subTest(name):
                assert_that(printed(name), equal_to("state"))

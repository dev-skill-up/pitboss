"""After a Plan is approved, a review prints it as fixed (pitboss#187)."""

import argparse
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, config, forms, gradeline, planfixed
from .briefmake import pinned
from .linting import HEAD, lines, lint, write_text

FORM = config.ReviewForm(
    lines=config.DEFAULT_FORM, approved="approved", changes_needed="changes needed"
)
FIXED = "Plan: approved (fixed)"
RULE = (
    "A gap you see in the Plan is a request for an Opus ruling, never a Plan"
    " finding."
)
START = f"## Review\nReviewed: {HEAD}\nVerdict: approved\n"


def graded(plan: str) -> str:
    """A review in the generic form with a Plan line.

    Args:
        plan: the Plan line.

    Returns:
        The review.
    """
    return f"{START}{plan}\nExecution: approved\n"


def refused(body: str) -> Sequence[str]:
    """The findings of a review of an approved Plan.

    Args:
        body: the review.

    Returns:
        The findings of ``plan_fixed``.
    """
    on = argparse.Namespace(plan_approved=True)
    return planfixed.required(on, forms.Subject(name="x", body=body, head=""), FORM)


class TestPlanFixed(unittest.TestCase):
    """The brief carries the rule and the lint refuses a review that breaks it."""

    def test_the_fixed_line_is_accepted(self) -> None:
        """Done-when 2: exactly the fixed Plan line passes."""
        assert_that(refused(graded(FIXED)), equal_to([]))

    def test_any_other_plan_verdict_is_refused(self) -> None:
        """Done-when 2: carried, approved, changes needed, none, or two lines."""
        for plan in (
            "Plan: approved",
            "Plan: changes needed",
            "Plan: approved (carried over)",
            "",
            f"{FIXED}\nPlan: changes needed",
            f"{FIXED}\n{FIXED}",
        ):
            found = refused(graded(plan))
            assert_that(len(found), equal_to(1))
            assert_that(found[0], contains_string("(plan-fixed)"))

    def test_the_command_refuses_only_with_the_flag(self) -> None:
        """`lint review --plan-approved` is 1 for a changed Plan, 0 for the fixed."""
        changed = write_text("changed.md", graded("Plan: changes needed"))
        fixed = write_text("fixed.md", graded(FIXED))
        head = ("--head", HEAD)
        ran = [
            lint("review", changed, *head),
            lint("review", changed, *head, "--plan-approved"),
            lint("review", fixed, *head, "--plan-approved"),
            lint("review", changed, *head, "--plan-approved", "--gated"),
            lint("review", fixed, *head, "--plan-approved", "--gated"),
        ]
        assert_that([each.code for each in ran], equal_to([0, 1, 0, 1, 0]))
        assert_that(lines(ran[1])[0], contains_string("(plan-fixed)"))
        assert_that(lines(ran[3])[0], contains_string("(plan-fixed)"))
        assert_that(lines(ran[4]), equal_to(["ok"]))

    def test_the_fixed_line_reads_as_an_approved_plan(self) -> None:
        """The flow still reads the fixed line as the Plan's approval."""
        grade = gradeline.line_approved
        approved, changes = "approved", "changes needed"
        assert_that(grade(FIXED, "Plan: ", approved, changes), equal_to(True))
        assert_that(
            grade("Plan: changes needed", "Plan: ", approved, changes), equal_to(False)
        )
        assert_that(
            grade("Plan: changes needed (fixed)", "Plan: ", approved, changes),
            equal_to(None),
        )

    def test_the_briefs_say_it(self) -> None:
        """Done-when 1: the Execution review brief prints the line and the rule."""
        pinned(brief.Kind.REVIEW_EXECUTION, [FIXED, RULE])
        for kind in (
            brief.Kind.REVIEW_RESOLUTION,
            brief.Kind.REVIEW_FIX_ROUND,
            brief.Kind.REVIEW_RELOCK,
        ):
            pinned(kind, [FIXED])

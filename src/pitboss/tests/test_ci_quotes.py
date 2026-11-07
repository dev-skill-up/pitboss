"""The Execution review waits for the CI quotes the Plan names (pitboss#277).

bats-lang/quire#1058: an Opus ruling scheduled CI quotes after the PR is ready,
the sweep offered the Execution review as soon as the checks passed, and the
review rejected the missing quotes, which a ruling then escalated to the owner.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftextci, planbody, steps
from . import test_flow, test_flow_sweep, world
from .briefmake import pinned, text
from .test_commands import sweep

QUOTES_PLAN = "## Plan\n1. CI quote: the Run Nox step of the head\n"
PLAN_ONLY_APPROVED = test_flow_sweep.graded("approved", None, 1)
WANTED = "add the CI quotes to the body"
QUOTED = "## Execution\nCI quote: check.yml, job 5, step Run Nox, `3 passed`\n"
UNQUOTED = "## Execution\nthe work\n"


def body(plan: str, execution: str) -> str:
    """A PR body.

    Args:
        plan: the Plan section.
        execution: the Execution section.

    Returns:
        The body.
    """
    return f"Fixes #7\n\n{plan}\n{execution}"


class TestRead(unittest.TestCase):
    """What the body is read as."""

    def test_missing_quotes_are_told_from_given_ones(self) -> None:
        """Fewer quotes than the Plan has rows are missing."""
        two = "## Plan\nthe CI quote of a\nand the CI quotes of b\n"
        cases = {
            (QUOTES_PLAN, UNQUOTED): True,
            (QUOTES_PLAN, QUOTED): False,
            (QUOTES_PLAN, "## Execution\n- **CI quote:** x\n"): False,
            (two, QUOTED): True,
            (two, QUOTED + "CI quotes: y\n"): False,
            ("## Plan\nthe plan\n", UNQUOTED): False,
            ("## Plan\nthe plan\n", QUOTED): False,
        }
        for (plan, execution), want in cases.items():
            made = planbody.ci_quotes_missing(body(plan, execution))
            assert_that(made, equal_to(want))

    def test_a_quote_line_in_the_plan_is_no_quote_given(self) -> None:
        """Only the Execution section answers the rows."""
        assert_that(
            planbody.ci_quotes_missing(body(QUOTES_PLAN, "## Review\nCI quote: x\n")),
            equal_to(True),
        )


class TestFlow(unittest.TestCase):
    """The step of a ready PR with green checks."""

    def test_the_worker_adds_the_quotes_before_any_review(self) -> None:
        """Plan approved, checks green, quotes missing: a worker, no review."""
        pr = test_flow.state(
            test_flow.graded(*test_flow.PLAN_APPROVED_ALONE, 1),
            body=body(QUOTES_PLAN, UNQUOTED),
        )
        test_flow.expect(steps.worker(steps.Task.ADD_CI_QUOTES), pr)

    def test_the_review_is_offered_once_the_quotes_are_there(self) -> None:
        """With the quotes in the body the Execution is reviewed."""
        pr = test_flow.state(
            test_flow.graded(*test_flow.PLAN_APPROVED_ALONE, 1),
            body=body(QUOTES_PLAN, QUOTED),
        )
        want = steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN)
        test_flow.expect(want, pr)

    def test_a_plan_without_quote_rows_is_reviewed_as_before(self) -> None:
        """The state needs the Plan's rows."""
        pr = test_flow.state(test_flow.graded(*test_flow.PLAN_APPROVED_ALONE, 1))
        want = steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN)
        test_flow.expect(want, pr)


class TestSweep(unittest.TestCase):
    """The sweep of a ready PR with green checks and a Plan with CI-quote rows."""

    def test_the_sweep_names_the_step_and_offers_no_review(self) -> None:
        """Done-when: the next step is `add the CI quotes to the body`."""
        here = test_flow_sweep.world_with(
            [PLAN_ONLY_APPROVED], body=body(QUOTES_PLAN, UNQUOTED), draft=False
        )
        printed = sweep(here).out
        assert_that(printed, contains_string(WANTED))
        assert_that("review=" in printed.split("project#3")[-1], equal_to(False))
        nexts = world.invoke(here, "next", here.config, "#7", "--now", world.FUTURE).out
        assert_that(nexts, contains_string(WANTED))
        assert_that("REGULAR_REVIEW" in nexts, equal_to(False))


class TestBriefs(unittest.TestCase):
    """The briefs of the ruling, the reviews and the worker."""

    def test_the_ruling_brief_asks_for_no_pasted_ci_output(self) -> None:
        """(c): a ruling points to the run, never asks for log lines."""
        pinned(brief.Kind.RULING, [brieftextci.RULING_NO_CI_QUOTES])
        assert_that(
            brieftextci.RULING_NO_CI_QUOTES,
            contains_string("never ask for CI log lines or pasted CI output"),
        )

    def test_the_execution_reviews_accept_a_ci_pointer(self) -> None:
        """The reviewer never demands quoted log lines for a CI row."""
        for kind in (brief.Kind.REVIEW_FULL, brief.Kind.REVIEW_EXECUTION):
            pinned(kind, [brieftextci.REVIEW_CI_ACCEPTED])
        assert_that(
            brieftextci.REVIEW_CI_ACCEPTED,
            contains_string("never ask for quoted log lines"),
        )
        assert_that(
            brieftextci.REVIEW_CI_ACCEPTED in text(brief.Kind.REVIEW_PLAN),
            equal_to(False),
        )

    def test_the_worker_brief_adds_the_quotes_as_pointers(self) -> None:
        """The worker's task names the pointer and pastes no output."""
        pinned(brief.Kind.ADD_CI_QUOTES, ["paste no log output", "CI quote:"])

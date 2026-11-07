"""The Execution review waits for the CI quotes the Plan names (pitboss#277).

bats-lang/quire#1058: an Opus ruling scheduled CI quotes after the PR is ready,
the sweep offered the Execution review as soon as the checks passed, and the
review rejected the missing quotes, which a ruling then escalated to the owner.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brief, brieftextci, planbody, steps
from . import test_flow, test_flow_sweep, test_plan_commands
from .briefmake import pinned, text

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

    def test_the_step_follows_the_quotes_the_plan_names(self) -> None:
        """Quotes missing: a worker, no review; given or not named: the review."""
        review = steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN)
        cases = [
            (body(QUOTES_PLAN, UNQUOTED), steps.worker(steps.Task.ADD_CI_QUOTES)),
            (body(QUOTES_PLAN, QUOTED), review),
            (test_flow.BODY, review),
        ]
        approved = test_flow.graded(test_flow.APPROVED, None, 1)
        for text_of_body, want in cases:
            made = test_flow.state(approved, body=text_of_body)
            test_flow.expect(want, made)


class TestSweep(unittest.TestCase):
    """The sweep of a ready PR with green checks and a Plan with CI-quote rows."""

    def test_the_list_names_the_step_and_offers_no_review(self) -> None:
        """Done-when: the next step is `add the CI quotes to the body`."""
        here = test_flow_sweep.world_with(
            [PLAN_ONLY_APPROVED], body=body(QUOTES_PLAN, UNQUOTED), draft=False
        )
        listed = "".join(test_flow_sweep.listed_for_third(here))
        assert_that(listed, contains_string(f"({WANTED},"))
        assert_that("review it" in listed, equal_to(False))


class TestBriefs(unittest.TestCase):
    """The briefs of the ruling, the reviews and the worker."""

    def test_the_ruling_asks_for_no_pasted_output_and_reviews_accept_a_pointer(
        self,
    ) -> None:
        """(c): a ruling points to the run; a CI row's pointer is the evidence."""
        pinned(brief.Kind.RULING, [brieftextci.RULING_NO_CI_QUOTES])
        for kind in test_plan_commands.EXECUTION_REVIEWS:
            pinned(kind, [brieftextci.REVIEW_CI_ACCEPTED])
        assert_that(
            brieftextci.RULING_NO_CI_QUOTES,
            contains_string("never ask for CI log lines or pasted CI output"),
        )
        assert_that(
            brieftextci.REVIEW_CI_ACCEPTED in text(brief.Kind.REVIEW_PLAN),
            equal_to(False),
        )

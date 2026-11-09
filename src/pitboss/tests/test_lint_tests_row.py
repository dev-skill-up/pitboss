"""A Plan that adds or loosens a lint needs a refusal-test row (pitboss#358)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import expansion, linttests, plancommands, plandigest, planrow

ADDS = "## Plan\n1. `$ make test` The new check refuses a bare sleep.\n"
TESTED = (
    "## Plan\n1. `$ make test` The new check refuses a bare sleep.\n"
    "2. Test the nearest input, which the check must still reject.\n"
)
PLAIN = "## Plan\n1. `$ make test` Fix the typo in the heading.\n"


def found(body: str, approved: Sequence[str] = ()) -> Sequence[str]:
    """The findings of the rule for a body.

    Args:
        body: the PR body.
        approved: the digests of the approved Plans.

    Returns:
        The findings.
    """
    return linttests.findings("b", body, planrow.rows(body), approved)


class TestTheRefusalTestRow(unittest.TestCase):
    """The rule, and the inputs next to it."""

    def test_a_plan_that_adds_a_check_without_the_row_is_refused(self) -> None:
        """Done-when: the finding names the line."""
        assert_that(found(ADDS), has_length(1))
        assert_that(found(ADDS)[0], contains_string("Plan line 2"))
        assert_that(found(ADDS)[0], contains_string("(lint-test)"))

    def test_the_row_for_the_nearest_input_satisfies_it(self) -> None:
        """A numbered row that says the input is still rejected."""
        assert_that(found(TESTED), equal_to([]))

    def test_the_row_must_be_numbered(self) -> None:
        """The nearest input: the words in prose, not in a row."""
        prose = ADDS + "\nThe nearest input must still reject.\n"
        assert_that(found(prose), has_length(1))

    def test_each_spelling_of_the_trigger_is_read(self) -> None:
        """New, loosened, added, relaxed; a lint, a check, an exemption."""
        for said in ("A loosened lint", "It adds an exemption", "relaxes the check"):
            with self.subTest(said):
                assert_that(found(f"## Plan\n1. {said}.\n"), has_length(1))

    def test_a_plan_that_changes_no_lint_has_no_finding(self) -> None:
        """Most Plans."""
        assert_that(found(PLAIN), equal_to([]))

    def test_an_approved_plan_is_not_judged(self) -> None:
        """An approved Plan is never reopened (plan-approved)."""
        digest = expansion.section_digest(plandigest.section(ADDS))
        assert_that(found(ADDS, [digest]), equal_to([]))

    def test_pr_body_carries_it(self) -> None:
        """`pitboss lint pr-body` runs it."""
        said = plancommands.findings("b", ADDS)
        assert_that(" ".join(said).count("(lint-test)"), equal_to(1))

"""A Plan that adds or loosens a lint needs a refusal-test row (pitboss#358)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import bodydigest, forms, linttests, plandigest

ADDS = "## Plan\n1. `$ make test` The new check refuses a bare sleep.\n"
TESTED = (
    "## Plan\n1. `$ make test` The new check refuses a bare sleep.\n"
    "2. Test the nearest input, which the check must still reject.\n"
)
PLAIN = "## Plan\n1. `$ make test` Fix the typo in the heading.\n"


class TestTheRefusalTestRow(unittest.TestCase):
    """The rule, and the inputs next to it."""

    def test_a_plan_that_adds_a_check_without_the_row_is_refused(self) -> None:
        """Done-when: the finding names the line."""
        found = linttests.findings("b", ADDS)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("Plan line 2"))
        assert_that(found[0], contains_string("(lint-test)"))

    def test_the_row_for_the_nearest_input_satisfies_it(self) -> None:
        """A numbered row that says the input is still rejected."""
        assert_that(linttests.findings("b", TESTED), equal_to([]))

    def test_the_row_must_be_numbered(self) -> None:
        """The nearest input: the words in prose, not in a row."""
        prose = ADDS + "\nThe nearest input must still reject.\n"
        assert_that(linttests.findings("b", prose), has_length(1))

    def test_loosened_and_exemption_are_read_too(self) -> None:
        """Every spelling of the trigger."""
        for said in ("A loosened lint", "It adds an exemption", "relaxes the check"):
            with self.subTest(said):
                assert_that(
                    linttests.findings("b", f"## Plan\n1. {said}.\n"), has_length(1)
                )

    def test_a_plan_that_changes_no_lint_has_no_finding(self) -> None:
        """Most Plans."""
        assert_that(linttests.findings("b", PLAIN), equal_to([]))

    def test_an_approved_plan_is_not_judged(self) -> None:
        """An approved Plan is never reopened (plan-approved)."""
        digest = bodydigest.of_section(plandigest.section(ADDS))
        assert_that(linttests.findings("b", ADDS, [digest]), equal_to([]))

    def test_pr_body_carries_it(self) -> None:
        """`pitboss lint pr-body` runs it."""
        subject = forms.Subject(name="b", body=ADDS, head="")
        found = forms.pr_body(subject, [])
        assert_that(any("(lint-test)" in each for each in found), equal_to(True))

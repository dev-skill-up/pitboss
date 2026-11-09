"""A row meant as a CI pointer that is none, and a cited line gone (pitboss#358)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import cipointer, cipointercheck, plancheck

GOOD = "3. Workflow `check.yml`, job `check`, step `Run Nox`, greppable `test_a`.\n"
WEAK = "3. Workflow `ci` of this repository, its job, the step `Run Nox`.\n"
HEADED = "CI pointer rows\n\n3. The tests run in CI.\n"
FENCED = "```\nWorkflow `ci` job `x`\n```\n"
FILE = "one\ntwo\nthree\n"


def section(text: str) -> str:
    """A Plan section.

    Args:
        text: its lines after the heading.

    Returns:
        The section.
    """
    return "## Plan\n" + text


def head(text: str | None) -> cipointercheck.Read:
    """A reader of the head that has one file.

    Args:
        text: the file's text, None for no file.

    Returns:
        The reader.
    """
    return lambda _: text


class TestTheFormOfAPointer(unittest.TestCase):
    """The row `Workflow `ci`` is refused and a well-formed pointer is not."""

    def test_the_weak_row_is_refused_beside_the_good_one_accepted(self) -> None:
        """Done-when: both rows, one Plan."""
        found = cipointercheck.form_findings(section(GOOD + WEAK))
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("Plan line 3"))
        assert_that(found[0], contains_string("greppable `test_name`"))
        assert_that(cipointercheck.form_findings(section(GOOD)), equal_to([]))

    def test_a_row_under_the_heading_must_be_a_pointer(self) -> None:
        """The heading `CI pointer rows` makes every row below it a pointer."""
        assert_that(cipointercheck.form_findings(section(HEADED)), has_length(1))
        good = section("CI pointer rows\n\n" + GOOD)
        assert_that(cipointercheck.form_findings(good), equal_to([]))

    def test_a_row_under_another_heading_is_not_judged(self) -> None:
        """The rows after `Command rows` are not pointers."""
        text = "CI pointer rows\n\n" + GOOD + "Command rows\n\n1. Run it.\n"
        assert_that(cipointercheck.form_findings(section(text)), equal_to([]))

    def test_a_workflow_file_without_a_name_is_no_pointer(self) -> None:
        """The nearest input: the file named, no job, step or greppable."""
        text = "3. Workflow `check.yml`, job in it.\n"
        assert_that(cipointercheck.form_findings(section(text)), has_length(0))
        named = "3. The job `build` of the workflow runs.\n"
        assert_that(cipointercheck.form_findings(section(named)), has_length(1))

    def test_fenced_text_is_not_a_row(self) -> None:
        """Output of a command or a quoted text does not count."""
        assert_that(cipointercheck.form_findings(section(FENCED)), equal_to([]))
        assert_that(cipointer.read(section(FENCED)), equal_to([]))

    def test_plan_check_counts_it_as_a_pointer_finding(self) -> None:
        """The verdict says how many."""
        found = cipointercheck.form_findings(section(WEAK))
        verdict = plancheck.verdict([], found)
        assert_that(verdict, contains_string("CI pointer findings: 1"))


class TestACitedLine(unittest.TestCase):
    """A `path:line` of the prose is resolved at the head."""

    def test_a_line_the_file_has_is_accepted(self) -> None:
        """Line 3 of a three-line file."""
        found = cipointercheck.citation_findings(section("See a/b.py:3.\n"), head(FILE))
        assert_that(found, equal_to([]))

    def test_a_line_past_the_end_is_refused(self) -> None:
        """The nearest input: line 4 of a three-line file."""
        found = cipointercheck.citation_findings(section("See a/b.py:4.\n"), head(FILE))
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("the file has 3 lines"))

    def test_a_file_gone_with_a_directory_is_refused(self) -> None:
        """A path with a directory that the head does not have."""
        found = cipointercheck.citation_findings(section("See a/b.py:1.\n"), head(None))
        assert_that(found[0], contains_string("the file is not at the head"))

    def test_a_host_and_a_port_is_not_a_citation(self) -> None:
        """No directory, no file: nothing to resolve."""
        found = cipointercheck.citation_findings(
            section("See example.com:8080.\n"), head(None)
        )
        assert_that(found, equal_to([]))

    def test_a_disposition_line_is_the_impact_checks(self) -> None:
        """`file:line: edited` is judged against the hits, not here."""
        text = "a/b.py:99: edited\n"
        assert_that(
            cipointercheck.citation_findings(section(text), head(FILE)), equal_to([])
        )

"""A row meant as a CI pointer that is none, and a cited line gone (pitboss#358)."""

import unittest
from typing import Sequence

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


def form(text: str) -> Sequence[str]:
    """The form findings of a Plan.

    Args:
        text: its lines after the heading.

    Returns:
        The findings.
    """
    return cipointercheck.form_findings(section(text))


def cites(text: str, file: str | None = FILE) -> Sequence[str]:
    """The citation findings of a Plan, the head having one file.

    Args:
        text: its lines after the heading.
        file: the file's text at the head, None for no file.

    Returns:
        The findings.
    """
    return cipointercheck.citation_findings(section(text), lambda _: file)


class TestTheFormOfAPointer(unittest.TestCase):
    """The row `Workflow `ci`` is refused and a well-formed pointer is not."""

    def test_the_weak_row_is_refused_beside_the_good_one_accepted(self) -> None:
        """Done-when: both rows, one Plan."""
        refused = form(GOOD + WEAK)
        assert_that(refused, has_length(1))
        said = " ".join(refused)
        assert_that(said, contains_string("Plan line 3"))
        assert_that(said, contains_string("greppable `test_name`"))
        assert_that(form(GOOD), equal_to([]))

    def test_a_row_under_the_heading_must_be_a_pointer(self) -> None:
        """The heading `CI pointer rows` makes every row below it a pointer."""
        assert_that(form(HEADED), has_length(1))
        assert_that(form("CI pointer rows\n\n" + GOOD), equal_to([]))

    def test_a_row_under_another_heading_is_not_judged(self) -> None:
        """The rows after `Command rows` are not pointers."""
        text = "CI pointer rows\n\n" + GOOD + "Command rows\n\n1. Run it.\n"
        assert_that(form(text), equal_to([]))

    def test_the_names_of_a_row_decide_whether_it_is_judged(self) -> None:
        """The nearest input: a workflow file with no job, step or greppable name."""
        meant = {"3. Run `make test` in the job.\n": 0}
        meant["3. Workflow `check.yml`, job in it.\n"] = 1
        meant["3. The job `build` of the workflow runs.\n"] = 1
        for row, count in meant.items():
            assert_that(form(row), has_length(count))

    def test_fenced_text_is_not_a_row(self) -> None:
        """Output of a command or a quoted text does not count."""
        assert_that(form(FENCED), equal_to([]))
        assert_that(cipointer.read(section(FENCED)), equal_to([]))

    def test_plan_check_counts_it_as_a_pointer_finding(self) -> None:
        """The verdict says how many."""
        verdict = plancheck.verdict([], form(WEAK))
        assert_that(verdict, contains_string("CI pointer findings: 1"))


class TestACitedLine(unittest.TestCase):
    """A `path:line` of the prose is resolved at the head."""

    def test_a_line_the_file_has_is_accepted(self) -> None:
        """Line 3 of a three-line file."""
        assert_that(cites("See a/b.py:3.\n"), equal_to([]))

    def test_a_line_past_the_end_is_refused(self) -> None:
        """The nearest input: line 4 of a three-line file."""
        assert_that(cites("See a/b.py:4.\n"), has_length(1))
        assert_that(cites("See a/b.py:4.\n")[0], contains_string("has 3 lines"))

    def test_a_file_gone_with_a_directory_is_refused(self) -> None:
        """A path with a directory that the head does not have."""
        found = cites("See a/b.py:1.\n", None)
        assert_that(found[0], contains_string("the file is not at the head"))

    def test_what_is_not_a_file_citation_is_left_alone(self) -> None:
        """A host and port."""
        assert_that(cites("See example.com:8080.\n", None), equal_to([]))

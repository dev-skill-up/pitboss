"""A30 no scratch paths, I11 the Execution is kept, I25 CI pointers are given.

Rule ids A30, I11 and I25 of ``rules.tsv`` (pitboss#444, items 22, 11 and 25).
"""

import unittest

from hamcrest import assert_that, contains_string, empty, has_length

from .. import bodyrules

JOB = "https://github.com/o/r/actions/runs/1/job/2"


class TestScratch(unittest.TestCase):
    """A Plan row reads nothing from a scratch path."""

    def test_a30_a_row_reading_a_scratchpad_is_refused(self) -> None:
        """Quire 1104: a row ran against another session's scratchpad."""
        body = "## Plan\n1. `cat /tmp/claude-0/x/scratchpad/m3.txt`\n"
        found = bodyrules.scratch_findings(body)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("Plan row 1"))
        assert_that(found[0], contains_string("/tmp/claude-0/x/scratchpad/m3.txt"))

    def test_a30_a_row_making_its_own_directory_passes(self) -> None:
        """A directory the row makes itself is allowed."""
        body = "## Plan\n1. `mkdir /tmp/work && cat /tmp/work/a`\n"
        assert_that(bodyrules.scratch_findings(body), empty())

    def test_a30_a_configured_scratch_root_is_refused(self) -> None:
        """The config's scratch directories count as well as /tmp."""
        body = "## Plan\n1. `cat /var/scratch/a`\n"
        assert_that(bodyrules.scratch_findings(body, ["/var/scratch"]), has_length(1))


class TestSection(unittest.TestCase):
    """A body with code commits keeps its Execution."""

    def test_i11_a_body_without_execution_is_refused(self) -> None:
        """Pitboss 469 lost its Execution in a regex edit."""
        found = bodyrules.section_findings("## Plan\nx\n")
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("## Execution"))

    def test_i11_a_body_with_execution_passes(self) -> None:
        """The section present, or no code commits, is no finding."""
        assert_that(bodyrules.section_findings("## Execution\nx\n"), empty())


class TestPointers(unittest.TestCase):
    """Plan rows that point to CI have pointers in the Execution."""

    def test_i25_two_rows_without_pointers_are_named(self) -> None:
        """Pitboss 473: 22 rows with no job URL passed."""
        body = "## Plan\n1. CI shows a\n2. CI shows b\n\n## Execution\nnothing\n"
        found = bodyrules.pointer_findings(body)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("row 1, 2"))

    def test_i25_rows_with_pointers_pass(self) -> None:
        """Each row has its run and job URL, workflow, step and string."""
        line = f"Row {{n}}: {JOB} check.yml step `Run Nox` greppable `test_x`\n"
        body = (
            "## Plan\n1. CI shows a\n2. CI shows b\n\n## Execution\n"
            + line.format(n=1)
            + line.format(n=2)
        )
        assert_that(bodyrules.pointer_findings(body), empty())

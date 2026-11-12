"""A30 no scratch paths, I11 the Execution is kept, I25 CI pointers are given.

Rule ids A30, I11 and I25 of ``rules.tsv`` (pitboss#444, items 22, 11 and 25).
"""

import unittest

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import bodyrules, plancheck
from ..textparts import starting

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


def named(command: str) -> int:
    """How many outside-path findings a one-row Plan of a command gets.

    Args:
        command: the command of row 1.

    Returns:
        The count.
    """
    return len(bodyrules.path_findings(f"## Plan\n1. `{command}`\n"))


class TestOutsidePath(unittest.TestCase):
    """A35: a Plan row names no path outside the repository (rp#683)."""

    def test_a35_a_row_running_a_script_of_the_scratchpad_is_refused(self) -> None:
        """Rp 683: row 1 ran a script kept in a session scratchpad."""
        body = "## Plan\n1. `bash /home/user/scratchpad/check.sh`\n"
        found = bodyrules.path_findings(body)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("plan-path: Plan row 1"))
        assert_that(found[0], contains_string("/home/user/scratchpad/check.sh"))

    def test_a35_each_kind_of_outside_path_is_refused(self) -> None:
        """An absolute path of a system root, the home directory, a variable."""
        paths = ("/home/u/repo/x.sh", "/Users/u/x", "~/x.py", "$HOME/x", "/opt/x")
        assert_that([named(f"python {each}") for each in paths], equal_to([1] * 5))

    def test_a35_paths_of_the_checkout_and_the_system_pass(self) -> None:
        """Relative paths, system programs, URLs, API paths and sed patterns."""
        commands = (
            "bats test src/x.bats",
            "/usr/bin/env python3 -c pass",
            "cat /dev/null",
            "gh api /repos/o/r/pulls",
            "sed -n '/foo/p' src/a.py",
            "curl https://example.org/tmp/x",
        )
        assert_that([named(each) for each in commands], equal_to([0] * 6))

    def test_a35_a_directory_the_row_makes_passes_and_a_tmp_path_is_a30s(self) -> None:
        """A /tmp path is plan-scratch's; the two checks never name it twice."""
        own = "## Plan\n1. `mkdir -p /opt/w && ls /opt/w`\n"
        assert_that(bodyrules.path_findings(own), empty())
        scratch = "## Plan\n1. `cat /tmp/x/scratchpad/m`\n"
        assert_that(bodyrules.path_findings(scratch), empty())
        assert_that(bodyrules.scratch_findings(scratch), has_length(1))

    def test_a35_plan_check_refuses_the_body_and_counts_the_finding(self) -> None:
        """The check is part of ``plan-check``: its findings and its last line."""
        body = "## Plan\n1. `bash /home/user/scratchpad/check.sh`\n"
        found = plancheck.form_findings(body, body, [])
        assert_that(starting(found, "plan-path"), has_length(1))
        said = plancheck.verdict([], found)
        assert_that(said, contains_string("Outside path findings: 1"))

    def test_a30_mktemp_does_not_make_every_tmp_path_the_rows_own(self) -> None:
        """A row with `mktemp` and a literal /tmp script is still refused."""
        body = "## Plan\n1. `d=$(mktemp -d) && bash /tmp/s/check.sh`\n"
        assert_that(bodyrules.scratch_findings(body), has_length(1))


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

    def test_i25_a_body_without_execution_names_the_rows(self) -> None:
        """No Execution at all holds no pointer."""
        found = bodyrules.pointer_findings("## Plan\n1. CI shows a\n")
        assert_that(found, has_length(1))

    def test_i25_rows_with_pointers_pass(self) -> None:
        """Each row has its run and job URL, workflow, step and string."""
        line = f"Row {{n}}: {JOB} check.yml step `Run Nox` greppable `test_x`\n"
        body = (
            "## Plan\n1. CI shows a\n2. CI shows b\n\n## Execution\n"
            + line.format(n=1)
            + line.format(n=2)
        )
        assert_that(bodyrules.pointer_findings(body), empty())

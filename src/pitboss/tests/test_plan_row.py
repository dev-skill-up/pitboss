"""A Plan row names the whole command its Evidence line ran (pitboss#259)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import (
    assert_that,
    contains_string,
    empty,
    equal_to,
    has_length,
)

from .. import forms, planrow
from .linting import HEAD
from .test_commands import sweep
from .test_flow_sweep import world_with
from .test_plan_command_lint import body_of as plan_body

COMMAND = "sha256sum a.txt b.txt c.txt"
# each case: the Plan's rows, the commands the Evidence ran, the check names
# that mention the numbers of the refused rows
CASES: Mapping[str, tuple[Sequence[str], Sequence[str], Sequence[int]]] = {
    "the whole command": ([f"hash `{COMMAND}`"], [COMMAND], []),
    "a pipe after it": ([f"hash `{COMMAND}`"], [COMMAND + " | head -1"], []),
    "a prose row": (["hash the three files with sha256sum"], [COMMAND], [1]),
    "a differing row": (["hash `sha256sum a.txt`"], [COMMAND], [1]),
    "a missing row": ([f"`{COMMAND}`"], [COMMAND, "git status"], [2]),
    "the second row": (
        [f"`{COMMAND}`", "status of the tree"],
        [COMMAND, "git status"],
        [2],
    ),
    "a span among prose": (
        [f"hash the files (`{COMMAND}`) and look"],
        [COMMAND],
        [],
    ),
    "no numbered row": ([], [COMMAND], []),
}


def body_of(plan_rows: Sequence[str], ran: Sequence[str]) -> str:
    """A body with numbered Plan rows and an Evidence that ran commands.

    Args:
        plan_rows: the text of each Plan row, numbered from 1.
        ran: the commands the Evidence ran.

    Returns:
        The body.
    """
    numbered = [f"{n}. {each}" for n, each in enumerate(plan_rows, 1)]
    return plan_body("\n".join(numbered) or "text only", ran)


def refused(body: str) -> Sequence[str]:
    """The plan-row findings of a body.

    Args:
        body: the body.

    Returns:
        The findings.
    """
    return planrow.findings("body", body)


def swept(row: str) -> str:
    """What the sweep prints for a PR whose Plan has one row.

    Args:
        row: the text of the row.

    Returns:
        The sweep's output.
    """
    return sweep(world_with([], body=body_of([row], [COMMAND]))).out


class TestPlanRow(unittest.TestCase):
    """The pairing of the Evidence lines with the Plan rows."""

    def test_each_case(self) -> None:
        """A prose row and a differing row are refused, the exact one passes."""
        for name, (rows, ran, bad) in CASES.items():
            with self.subTest(name):
                found = refused(body_of(rows, ran))
                assert_that(found, has_length(len(bad)))
                for number, each in zip(bad, found):
                    assert_that(each, contains_string(f"Plan row {number} "))
                    assert_that(each.endswith("(plan-row)"), equal_to(True))

    def test_the_three_findings_say_which_fault(self) -> None:
        """Prose, a differing string and a missing row are told apart."""
        prose = refused(body_of(["by hand"], [COMMAND]))[0]
        differs = refused(body_of(["`ls`"], [COMMAND]))[0]
        missing = refused(body_of(["`ls`"], ["ls", COMMAND]))[0]
        assert_that(prose, contains_string("does not name the whole command"))
        assert_that(differs, contains_string("the strings differ"))
        assert_that(missing, contains_string("has no row for the Evidence line"))

    def test_a_continuation_line_belongs_to_its_row(self) -> None:
        """A row that wraps still holds its command."""
        body = body_of([f"hash\n   `{COMMAND}`"], [COMMAND])
        assert_that(refused(body), empty())

    def test_lint_carries_it(self) -> None:
        """pr_body reports the prose row once, in the form of every finding."""
        body = body_of(["by hand"], [COMMAND])
        subject = forms.Subject(name="body", body=body, head=HEAD)
        found = forms.pr_body(subject)
        assert_that(sum("(plan-row)" in each for each in found), equal_to(1))

    def test_the_sweep_prints_the_line_for_a_prose_row_only(self) -> None:
        """The PLAN ROW line names the PR; an exact row has none."""
        rows = ["by hand", f"`{COMMAND}`"]
        named = ["PLAN ROW owner/project#3" in swept(each) for each in rows]
        assert_that(named, equal_to([True, False]))
        assert_that("PLAN ROW" in swept(rows[1]), equal_to(False))

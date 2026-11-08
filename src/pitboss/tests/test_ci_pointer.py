"""Tests for the CI pointers of a Plan (keyword: ci-pointer, pitboss#335)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import cipointer

QUIRE_ROW = (
    "## Plan\n\n"
    "10. CI pointers, last: workflow `.github/workflows/check.yml`, jobs `static"
    " (${{ matrix.group }})` and the `e2e` jobs, steps `Static tests` and `Run e2e"
    " tests` (greppable: `tests/static/run.sh`, `gen-pwa test`)\n"
)


def one(section: str) -> Sequence[object]:
    """The fields of the only pointer of a section.

    Args:
        section: the Plan section.

    Returns:
        Its line, workflow, jobs, steps and greppable strings.
    """
    (found,) = cipointer.read(section)
    return [found.line, found.workflow, found.jobs, found.steps, found.greppable]


class TestPointer(unittest.TestCase):
    """What a row names after the words job, step and greppable."""

    def test_a_row_with_every_part_is_read(self) -> None:
        """Lists joined by commas, and and the; a bare file name has its directory."""
        assert_that(
            one(QUIRE_ROW),
            equal_to(
                [
                    3,
                    ".github/workflows/check.yml",
                    ["static (${{ matrix.group }})", "e2e"],
                    ["Static tests", "Run e2e tests"],
                    ["tests/static/run.sh", "gen-pwa test"],
                ]
            ),
        )
        bare = (
            "## Plan\n1. workflow `pr-main.yml`, step `Run Nox`, greppable `test_a`\n"
        )
        assert_that(
            one(bare),
            equal_to([2, ".github/workflows/pr-main.yml", [], ["Run Nox"], ["test_a"]]),
        )

    def test_another_word_ends_a_list(self) -> None:
        """A command after the step is no step; a string after a title is one."""
        text = (
            "## Plan\n1. workflow `check.yml`, step `Run Nox`, found with `gh run"
            " list` for the head; greppable `x` and the test title `y`\n"
        )
        assert_that(
            one(text),
            equal_to([2, ".github/workflows/check.yml", [], ["Run Nox"], ["x", "y"]]),
        )
        other = "## Plan\n1. workflow `check.yml`, step `A`, then job `b`\n"
        assert_that(one(other)[2:], equal_to([["b"], ["A"], []]))

    def test_a_row_continues_on_the_next_lines_until_a_blank_line_or_an_item(
        self,
    ) -> None:
        """Rows are paragraphs and list items; a command line is no row."""
        text = (
            "## Plan\n$ echo `x.yml` step `y`\n- workflow `check.yml`\n  step `Run"
            " e2e tests`\n\n  greppable `z`\n- `other.yml` job `q`\n"
        )
        found = cipointer.read(text)
        assert_that(
            [(each.line, each.workflow, each.steps, each.jobs) for each in found],
            equal_to(
                [
                    (3, ".github/workflows/check.yml", ["Run e2e tests"], []),
                    (7, ".github/workflows/other.yml", [], ["q"]),
                ]
            ),
        )

    def test_a_row_that_is_no_pointer_is_not_read(self) -> None:
        """A workflow file with no job, step or greppable string; names with no file."""
        for text in (
            "## Plan\n1. edit `check.yml` to add a job\n",
            "## Plan\n1. step `Run e2e tests` of the workflow, greppable `x`\n",
            "## Plan\n1. see `config.toml` and `notes.md`, step `x`\n",
        ):
            with self.subTest(text):
                assert_that(cipointer.read(text), equal_to([]))

    def test_each_workflow_of_a_row_gets_the_names_after_it(self) -> None:
        """Two files in one row: a name belongs to the last file before it."""
        text = (
            "## Plan\n1. step `Before`, workflow `a.yml`, step `A`; workflow `b.yml`,"
            " job `B`\n"
        )
        found = cipointer.read(text)
        assert_that(
            [(each.workflow[-5:], each.jobs, each.steps) for each in found],
            equal_to([("a.yml", [], ["Before", "A"]), ("b.yml", ["B"], [])]),
        )

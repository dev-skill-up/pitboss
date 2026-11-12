"""Item 12: ``pitboss lint change`` fails a flow change with no rule or scenario.

A change to a module of the flow (next step, plans, reviews, rulings, slots) comes
with a change to ``rules.tsv`` or to ``tests/scenarios`` (pitboss#444, keyword:
flow-change).
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import flowfiles
from .linting import lint, write_text
from .says import says


def header(path: str) -> str:
    """The first lines of a file's part of a diff.

    Args:
        path: the file.

    Returns:
        The ``diff --git`` line and the old file's line.
    """
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n"


FLOW = header("src/pitboss/flow.py")
REGISTER = header("src/pitboss/rules.tsv")
SCENARIO = header("src/pitboss/tests/scenarios/x-1.json")
TEST = header("src/pitboss/tests/test_flow.py")
OTHER = header("src/pitboss/disk.py")


def change(diff: str) -> tuple[str, object]:
    """Run ``lint change`` on a diff.

    Args:
        diff: the diff's text.

    Returns:
        What it printed and its exit code.
    """
    done = lint("change", write_text("change.diff", diff))
    return done.out, done.code


class TestChange(unittest.TestCase):
    """A planted diff."""

    def test_lint_change_refuses_a_flow_module_with_no_row_or_scenario(self) -> None:
        """The planted diff: ``flow.py`` alone."""
        out, code = change(FLOW + TEST)
        assert_that(code, equal_to(1))
        assert_that(out, contains_string("flow-change: `src/pitboss/flow.py`"))

    def test_lint_change_passes_with_the_register_beside(self) -> None:
        """The nearest input it must still accept: ``rules.tsv`` changes too."""
        assert_that(change(FLOW + REGISTER), equal_to(("ok\n", 0)))

    def test_lint_change_passes_with_a_scenario_beside(self) -> None:
        """A timeline under ``tests/scenarios`` shows the change."""
        assert_that(change(FLOW + SCENARIO), equal_to(("ok\n", 0)))

    def test_lint_change_passes_a_diff_of_no_flow_module(self) -> None:
        """A test and a module of another area are not the flow."""
        assert_that(change(OTHER + TEST), equal_to(("ok\n", 0)))

    def test_lint_change_takes_one_diff(self) -> None:
        """Two files are a usage error."""
        files = [write_text(f"{name}.diff", FLOW) for name in "ab"]
        says(lint("change", *files).err, "not 2")

    def test_lint_change_names_each_family_of_the_flow(self) -> None:
        """Next step, plans, reviews, rulings, slots."""
        names = ("flowstate", "nextfound", "planrow", "reviews", "rulings", "slotcache")
        found = flowfiles.modules_of([f"src/pitboss/{each}.py" for each in names])
        assert_that(len(found), equal_to(len(names)))

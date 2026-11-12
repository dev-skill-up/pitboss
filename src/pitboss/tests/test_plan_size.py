"""plan-check warns of a Plan whose Evidence is far over the allowance (#396)."""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import plansize
from .briefmake import has_all
from .test_plan_check import checked
from .says import exits
from ..textparts import starting

ALLOWED = plansize.ALLOWANCE + plansize.LEEWAY
FIX = "the Done-when is to be fixed (a better design that produces a small list)"
NOT_SPLIT = "not met by splitting the overflow into comments"


def plan_of(*commands: str) -> str:
    """A body whose Plan runs commands.

    Args:
        *commands: the commands, a row each.

    Returns:
        The body.
    """
    return (
        "## Plan\nThe rows.\n\n"
        + "$ "
        + "\n$ ".join(commands)
        + "\n\n## Execution\nx\n"
    )


def prints(size: int) -> str:
    """A command that prints a number of bytes.

    Args:
        size: how many.

    Returns:
        The command.
    """
    return f"yes x | head -c {size}"


def warned(lines: Sequence[str]) -> Sequence[str]:
    """The warnings among the lines a check printed.

    Args:
        lines: the lines.

    Returns:
        The lines that start with the warning's name.
    """
    return starting(lines, "evidence-size: warning:")


EDGE = ALLOWED - len("c") - plansize.FRAMING
# each case: what the rows printed, which is within the allowance and its leeway
SILENT: Mapping[str, Sequence[tuple[str, int]]] = {
    "small output": [("echo hi", 3)],
    "no commands": [],
    "the allowance": [("c", plansize.ALLOWANCE)],
    "the edge of the leeway": [("c", EDGE)],
}
# each case: a Plan and how many warnings plan-check gives it
PLANS: Mapping[str, tuple[str, int]] = {
    "far over the allowance": (plan_of("true", prints(200000)), 1),
    "output that stays small": (plan_of("echo hi", prints(60000)), 0),
    "output on standard error": (plan_of(prints(200000) + " >&2"), 1),
    "a command that cannot start": (plan_of("no-such-command-for-plan-size"), 0),
}


class TestWarning(unittest.TestCase):
    """The text of the warning and when it is given."""

    def test_within_the_allowance_and_its_leeway_is_silent(self) -> None:
        """Done-when: 64KB, and a little more, is allowed."""
        for name, printed in SILENT.items():
            with self.subTest(name):
                assert_that(plansize.over_allowance(printed), equal_to([]))

    def test_a_little_over_the_leeway_warns(self) -> None:
        """Done-when: one byte past the leeway."""
        found = plansize.over_allowance([("c", EDGE + 1)])
        assert_that(len(found), equal_to(1))

    def test_far_over_warns_and_names_the_dominant_row(self) -> None:
        """Done-when: the row, its size, the fix, and not the overflow in comments."""
        printed = [("git log", 100), ("rg -n x src", 300000), ("echo hi", 3)]
        (found,) = plansize.over_allowance(printed)
        has_all(
            found,
            [
                "evidence-size: warning:",
                "row 2",
                "`rg -n x src`",
                "300000 bytes",
                "64KB",
                "99%",
                FIX,
                NOT_SPLIT,
            ],
        )

    def test_many_small_rows_that_add_up_warn(self) -> None:
        """Done-when: the sum is the Evidence, not a row."""
        (found,) = plansize.over_allowance([(f"c{n}", 10000) for n in range(8)])
        has_all(found, ["print 80040 bytes", "row 1"])


class TestCommand(unittest.TestCase):
    """``pitboss plan-check`` measures what the rows print."""

    def test_each_plan_is_warned_of_or_not(self) -> None:
        """Done-when: both streams count; a row that did not run adds none."""
        for name, (plan, count) in PLANS.items():
            with self.subTest(name):
                done = checked(plan)
                assert_that(len(warned(done.out.splitlines())), equal_to(count))

    def test_the_warning_names_the_row_and_refuses_nothing(self) -> None:
        """Done-when: 200000 bytes printed; the warning, and the Plan passes."""
        done = checked(PLANS["far over the allowance"][0])
        has_all(warned(done.out.splitlines())[0], ["row 2", FIX])
        passed = (done.code, done.out.endswith("\nPlan check: ok\n"))
        assert_that(passed, equal_to((0, True)))

    def test_a_row_that_did_not_run_is_refused(self) -> None:
        """A command that cannot start prints nothing, and the Plan is refused."""
        exits(checked(PLANS["a command that cannot start"][0]), 1)

"""plan-check warns of a Plan whose Evidence is far over the allowance (#396)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import plansize
from .test_plan_check import checked

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
    rows = "".join(f"$ {each}\n" for each in commands)
    return f"## Plan\nThe rows.\n\n{rows}\n## Execution\nx\n"


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
    return [each for each in lines if each.startswith("evidence-size: warning:")]


class TestWarning(unittest.TestCase):
    """The text of the warning and when it is given."""

    def test_a_small_plan_is_silent(self) -> None:
        """Done-when: small output, none at all."""
        assert_that(plansize.warnings([("echo hi", 3)]), equal_to([]))
        assert_that(plansize.warnings([]), equal_to([]))

    def test_the_allowance_and_its_leeway_are_silent(self) -> None:
        """Done-when: 64KB, and a little more, is allowed."""
        edge = ALLOWED - len("c") - plansize.FRAMING
        assert_that(plansize.warnings([("c", plansize.ALLOWANCE)]), equal_to([]))
        assert_that(plansize.warnings([("c", edge)]), equal_to([]))

    def test_a_little_over_the_leeway_warns(self) -> None:
        """Done-when: one byte past the leeway."""
        over = ALLOWED - len("c") - plansize.FRAMING + 1
        assert_that(len(plansize.warnings([("c", over)])), equal_to(1))

    def test_far_over_warns_and_names_the_dominant_row(self) -> None:
        """Done-when: the row, its size, the fix, and not the overflow in comments."""
        printed = [("git log", 100), ("rg -n x src", 300000), ("echo hi", 3)]
        (found,) = plansize.warnings(printed)
        for word in (
            "evidence-size: warning:",
            "row 2",
            "`rg -n x src`",
            "300000 bytes",
            "64KB",
            "99%",
            FIX,
            NOT_SPLIT,
        ):
            assert_that(found, contains_string(word))

    def test_many_small_rows_that_add_up_warn(self) -> None:
        """Done-when: the sum is the Evidence, not a row."""
        printed = [(f"c{each}", 10000) for each in range(8)]
        (found,) = plansize.warnings(printed)
        assert_that(found, contains_string("print 80040 bytes"))
        assert_that(found, contains_string("row 1"))


class TestCommand(unittest.TestCase):
    """``pitboss plan-check`` measures what the rows print."""

    def test_a_plan_far_over_the_allowance_is_warned_of_and_not_refused(self) -> None:
        """Done-when: 200000 bytes printed; the warning, and the Plan passes."""
        done = checked(plan_of("true", prints(200000)))
        lines = done.out.splitlines()
        found = warned(lines)
        assert_that(len(found), equal_to(1))
        assert_that(found[0], contains_string("row 2"))
        assert_that(found[0], contains_string(FIX))
        assert_that([done.code, lines[-1]], equal_to([0, "Plan check: ok"]))

    def test_a_small_plan_is_silent(self) -> None:
        """Done-when: a Plan whose rows print little has no warning."""
        done = checked(plan_of("echo hi", prints(60000)))
        assert_that(warned(done.out.splitlines()), equal_to([]))

    def test_the_standard_error_counts(self) -> None:
        """Done-when: output on standard error is Evidence too."""
        done = checked(plan_of(prints(200000) + " >&2"))
        assert_that(len(warned(done.out.splitlines())), equal_to(1))

    def test_a_row_that_did_not_run_adds_nothing(self) -> None:
        """A command that cannot start prints nothing, and the Plan is refused."""
        done = checked(plan_of("no-such-command-for-plan-size"))
        assert_that(warned(done.out.splitlines()), equal_to([]))
        assert_that(done.code, equal_to(1))

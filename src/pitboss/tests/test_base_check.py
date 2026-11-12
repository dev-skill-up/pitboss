"""``pitboss base-check``: a test that passes on the base proves nothing (#444).

A PR body's Plan rows name tests; each must fail on the base, or pass there with
the body saying why (``Already on main: TEST: REASON``); keyword: base-check.
"""

import argparse
import pathlib
import tempfile
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import basecheck, basecheck_commands
from .test_rules import ran

HERE = pathlib.Path(__file__)
BODY = "## Plan\n\n0. Each test. greppable `test_c13_a_flake_rerun_is_refused`\n"
ONE = "test_rerun_rule.test_c13_a_flake_rerun_is_refused"
NAME = "test_c13_a_flake_rerun_is_refused"
REASON = f"\nAlready on main: {NAME}: the refusal was there\n"


module_of = {NAME: "test_rerun_rule"}.get


def command(body: str, ref: str) -> tuple[int, str]:
    """Run ``base-check`` on a body against a base.

    Args:
        body: the PR body.
        ref: the base.

    Returns:
        The exit status and the standard output.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".md") as file:
        file.write(body)
        file.flush()
        args = argparse.Namespace(file=file.name, ref=ref, repo=str(HERE.parents[3]))
        return ran(basecheck_commands.base_check, args)


class TestTheRule(unittest.TestCase):
    """The verdict on planted results."""

    def test_the_names_are_the_tests_of_the_plan_rows(self) -> None:
        """A word that is no test's name is left out."""
        assert_that(basecheck.named(BODY, module_of), equal_to([ONE]))

    def test_a_test_that_fails_on_the_base_is_ok(self) -> None:
        """Planted: the base fails it."""
        line = basecheck.verdict(BODY, [ONE], {ONE: False})
        assert_that(line, equal_to("base check: ok"))

    def test_a_test_that_passes_on_the_base_with_no_reason_fails_the_check(
        self,
    ) -> None:
        """Planted: the base passes it and the body lists no reason."""
        line = basecheck.verdict(BODY, [ONE], {ONE: True})
        assert_that(line, equal_to(f"base check: FAILED {ONE}"))

    def test_a_listed_reason_excuses_a_test_that_passes_on_the_base(self) -> None:
        """``Already on main: TEST: REASON`` with a reason."""
        line = basecheck.verdict(BODY + REASON, [ONE], {ONE: True})
        assert_that(line, equal_to("base check: ok"))
        none = basecheck.verdict(
            BODY + f"\nAlready on main: {NAME}: \n", [ONE], {ONE: True}
        )
        assert_that(none, equal_to(f"base check: FAILED {ONE}"))


class TestTheCommand(unittest.TestCase):
    """``base-check`` runs the tests in a scratch worktree of the base."""

    def test_a_base_the_head_equals_fails_the_check_naming_the_test(self) -> None:
        """HEAD as the base: the test passes there, no reason is listed."""
        status, said = command(BODY, "HEAD")
        assert_that(status, equal_to(1))
        assert_that(said, contains_string(f"base check: FAILED {ONE}"))

    def test_a_listed_reason_makes_the_same_base_ok(self) -> None:
        """The control of the planted case."""
        status, said = command(BODY + REASON, "HEAD")
        assert_that([status, said], equal_to([0, "base check: ok\n"]))

    def test_a_name_no_test_module_defines_is_left_out(self) -> None:
        """A greppable that names no test of the head is no test to run."""
        body = "## Plan\n\n0. Each test. greppable `test_c13_nothing_defines_this`\n"
        status, said = command(body, "HEAD")
        assert_that([status, said], equal_to([0, "base check: ok\n"]))

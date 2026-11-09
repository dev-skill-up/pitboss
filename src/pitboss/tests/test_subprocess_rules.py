"""The tests keep a failed command readable and run one at a time (pitboss#402).

The rules are read from the syntax of the files of the tests (keyword: captured-run):
a function that keeps a command's output hands the process back or says the command,
the status and the error; no pool or thread runs a subprocess.
"""

import pathlib
import unittest
from collections.abc import Sequence

from hamcrest import assert_that, equal_to

from . import capture_cases, capturescan, pool_cases, poolscan, scanning

HERE = pathlib.Path(__file__).resolve().parent


def lines_of(found: Sequence[scanning.Finding]) -> Sequence[int]:
    """The lines of findings.

    Args:
        found: the findings.

    Returns:
        Their lines, in order.
    """
    return [each.line for each in found]


class TestSubprocessRules(unittest.TestCase):
    """The files of the tests, and the nearest inputs each rule must tell apart."""

    def test_the_files_of_the_tests_pass_both_rules(self) -> None:
        """No function there loses the command or the error; no pool runs one."""
        texts = scanning.sources(HERE)
        found = [
            *capturescan.lossy_in_files(texts),
            *poolscan.pooled_subprocesses(texts, scanning.sources(HERE.parent)),
        ]
        assert_that([scanning.shown(each) for each in found], equal_to([]))

    def test_a_function_that_loses_the_command_or_the_error_is_refused(self) -> None:
        """A status and booleans are refused; the process, or all three, pass."""
        found = {
            name: lines_of(capturescan.lossy_in_files({"x.py": text}))
            for name, (text, _) in capture_cases.CAPTURES.items()
        }
        assert_that(
            found,
            equal_to(
                {n: list(want) for n, (_, want) in capture_cases.CAPTURES.items()}
            ),
        )

    def test_a_pool_that_runs_a_subprocess_is_refused(self) -> None:
        """Arithmetic in a pool passes; a function that runs a command fails."""
        found = {
            name: lines_of(poolscan.pooled_subprocesses({"x.py": text}))
            for name, (text, _) in pool_cases.POOLS.items()
        }
        assert_that(
            found,
            equal_to({n: list(want) for n, (_, want) in pool_cases.POOLS.items()}),
        )

    def test_a_package_function_that_runs_a_subprocess_is_followed_from_a_test(
        self,
    ) -> None:
        """A pool of a test mapping a function outside the tests is refused."""
        found = poolscan.pooled_subprocesses(
            {"t.py": pool_cases.MAPS_PACKAGE}, {"gitutil.py": pool_cases.PACKAGE}
        )
        assert_that(lines_of(found), equal_to([8]))
        assert_that(
            lines_of(poolscan.pooled_subprocesses({"t.py": pool_cases.MAPS_PACKAGE})),
            equal_to([]),
        )

    def test_a_finding_names_the_file_the_line_and_the_function(self) -> None:
        """A finding reads as ``path:line: function: reason``."""
        status = capture_cases.CAPTURES["a status and booleans"][0]
        thread = pool_cases.POOLS["a function that runs a subprocess"][0]
        found = [
            *capturescan.lossy_in_files({"t.py": status}),
            *poolscan.pooled_subprocesses({"u.py": thread}),
        ]
        assert_that(
            [scanning.shown(each).split(": ")[:2] for each in found],
            equal_to([["t.py:5", "ran"], ["u.py:10", "run_one"]]),
        )

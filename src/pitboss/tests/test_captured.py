"""A command that fails in a test says the command, the status and what it wrote."""

import subprocess
import sys
import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import captured

SAYS_AND_FAILS = (
    "import sys; print('said'); print('boom', file=sys.stderr); sys.exit(3)"
)
COMMAND = [sys.executable, "-c", SAYS_AND_FAILS]


class TestCapturedRun(unittest.TestCase):
    """What ``captured`` keeps and raises."""

    def test_a_failure_names_the_command_the_status_and_the_error(self) -> None:
        """The cause of the failure holds all three, and the output."""
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            captured.run(COMMAND)
        cause = raised.exception.__cause__
        assert_that(
            [raised.exception.returncode, raised.exception.stderr, type(cause)],
            equal_to([3, "boom\n", AssertionError]),
        )
        for part in (repr(COMMAND), "exited 3", "'boom\\n'", "'said\\n'"):
            assert_that(str(cause), contains_string(part))

    def test_a_finished_command_is_handed_back_whatever_its_status(self) -> None:
        """The status, the output and the error are the process's."""
        done = captured.finished(COMMAND)
        assert_that(
            (done.args, done.returncode, done.stdout, done.stderr),
            equal_to((COMMAND, 3, "said\n", "boom\n")),
        )

    def test_merged_error_output_is_in_the_standard_output(self) -> None:
        """With ``merged`` the error is in the output and there is no other."""
        done = captured.merged(COMMAND)
        assert_that(
            (sorted(done.stdout.split()), done.stderr),
            equal_to((["boom", "said"], None)),
        )

    def test_a_success_is_handed_back(self) -> None:
        """A command that exits 0 raises nothing."""
        done = captured.run([sys.executable, "-c", "print('fine')"])
        assert_that((done.returncode, done.stdout), equal_to((0, "fine\n")))

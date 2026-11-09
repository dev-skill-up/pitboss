"""A command that fails in a test says the command, the status and what it wrote."""

import sys
import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import captured

SAYS_AND_FAILS = (
    "import sys; print('said'); print('boom', file=sys.stderr); sys.exit(3)"
)
COMMAND = [sys.executable, "-c", SAYS_AND_FAILS]


class TestCapturedRun(unittest.TestCase):
    """What ``captured.run`` keeps and raises."""

    def test_a_failure_names_the_command_the_status_and_the_error(self) -> None:
        """The message of the failure holds all three, and the output."""
        with self.assertRaises(captured.Failed) as raised:
            captured.run(COMMAND)
        text = str(raised.exception)
        assert_that(text, contains_string(repr(COMMAND)))
        assert_that(text, contains_string("exited 3"))
        assert_that(text, contains_string("'boom\\n'"))
        assert_that(text, contains_string("'said\\n'"))

    def test_an_unchecked_run_hands_back_the_process(self) -> None:
        """The status, the output and the error are the process's."""
        done = captured.run(COMMAND, check=False)
        assert_that(
            (done.args, done.returncode, done.stdout, done.stderr),
            equal_to((COMMAND, 3, "said\n", "boom\n")),
        )

    def test_merged_error_output_is_in_the_standard_output(self) -> None:
        """With ``merge`` the error is in the output and there is no other."""
        done = captured.run(COMMAND, check=False, merge=True)
        assert_that(
            (sorted(done.stdout.split()), done.stderr),
            equal_to((["boom", "said"], None)),
        )

    def test_a_success_is_handed_back(self) -> None:
        """A command that exits 0 raises nothing."""
        done = captured.run([sys.executable, "-c", "print('fine')"])
        assert_that((done.returncode, done.stdout), equal_to((0, "fine\n")))

    def test_the_description_is_the_text_of_the_failure(self) -> None:
        """``described`` of the process is what the failure says."""
        done = captured.run(COMMAND, check=False)
        with self.assertRaises(captured.Failed) as raised:
            captured.run(COMMAND)
        assert_that(str(raised.exception), equal_to(captured.described(done)))

"""A PR off a relock branch is pins-only by its files (pitboss#34, pins-only)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import config
from . import fakes
from . import pinsworld as pw

OK_LINE = "PINS-ONLY OK owner/project#3: pins-check printed OK"
RENAMED = [{"filename": "bats.lock", "previous_filename": "src/a.py"}]
CASES = {
    "pin files": (pw.PIN_FILES, True),
    "mixed": (pw.MIXED_FILES, False),
    "none": ([], False),
    "renamed from a source file": (RENAMED, False),
}


class TestFiles(unittest.TestCase):
    """The files decide."""

    def test_which_files_make_a_pr_pins_only(self) -> None:
        """Pin files and OK: no review; a source file, no file or a rename: review."""
        for label, (changed, merged) in CASES.items():
            with self.subTest(label):
                here = pw.make("branch-3", pw.OK_COMMAND, changed)
                out = pw.swept(here)
                assert_that(out.count(OK_LINE), equal_to(int(merged)))
                assert_that(pw.offered(here) == "", equal_to(merged))
                assert_that(bool(pw.ran_commands(here)), equal_to(merged))

    def test_pin_files_are_configured(self) -> None:
        """``pin_files`` replaces the default list."""
        extra = 'pin_files = ["requirements.txt"]\n'
        here = pw.make("branch-3", pw.OK_COMMAND, extra=extra)
        pw.files(here, [{"filename": "requirements.txt"}])
        assert_that(pw.swept(here), contains_string(OK_LINE))
        pw.files(here, pw.PIN_FILES)
        assert_that(pw.pins_lines(pw.swept(here)), equal_to(""))

    def test_a_draft_is_asked_nothing(self) -> None:
        """A draft's review is a Plan review: the command is not run."""
        here = pw.make("branch-3", pw.OK_COMMAND, pw.PIN_FILES, draft=True)
        assert_that(pw.pins_lines(pw.swept(here)), equal_to(""))
        assert_that(pw.ran_commands(here), equal_to([]))

    def test_the_library_is_told_to_merge_by_hand_with_the_reason(self) -> None:
        """MERGE BY HAND says the pins-check printed OK, in place of READY TO MERGE."""
        here = pw.with_library(pw.make("branch-3", pw.OK_COMMAND))
        want = "MERGE BY HAND owner/lib#4: green, clean, pins-only, pins-check printed"
        assert_that(pw.swept(here), contains_string(want))


class TestDefaultCommand(unittest.TestCase):
    """No pins_check_command: `bats pins-check` is run (pitboss#350)."""

    def test_the_head_is_run_through_bats_pins_check(self) -> None:
        """An empty command is the default; the sweep offers no review on OK."""
        here = pw.with_bats(pw.relock(""))
        out = pw.swept(here)
        words = ["env", "-C", str(here.clone), "bats", "pins-check", "origin/main"]
        (ran,) = pw.ran_commands(here)
        assert_that(ran, equal_to([*words, pw.HEAD, "--compiler", "../bats"]))
        assert_that(out, contains_string(OK_LINE))
        assert_that(pw.offered(here), equal_to(""))

    def test_a_missing_bats_is_said_and_the_pr_is_reviewed(self) -> None:
        """The default command that cannot run is a PINS-ONLY line, never silence."""
        here = pw.without_bats()
        out = pw.swept(here)
        assert_that(out, contains_string("pins-check did not print OK (env: "))
        assert_that(pw.offered(here), contains_string("(review it"))


class TestConfig(unittest.TestCase):
    """``[relock] pins_check_command`` and ``pin_files``."""

    def test_the_defaults_are_bats_pins_check_and_the_bats_files(self) -> None:
        """No key, or an empty one, is `bats pins-check` with `--compiler ../bats`."""
        found = fakes.settings(fakes.directory()).lint.pins
        assert_that(found, equal_to(config.Pins()))
        assert_that(found.files, equal_to(config.DEFAULT_PIN_FILES))
        want = "bats pins-check {base} {head} --compiler ../bats"
        assert_that(found.command, equal_to(want))
        empty = fakes.settings(fakes.directory(), pw.relock_table("")).lint.pins
        assert_that(empty.command, equal_to(found.command))

    def test_the_command_and_files_are_read(self) -> None:
        """Both keys of ``[relock]``."""
        extra = pw.relock_table("c {base}", 'pin_files = ["a"]\n')
        found = fakes.settings(fakes.directory(), extra).lint.pins
        assert_that((found.command, list(found.files)), equal_to(("c {base}", ["a"])))

    def test_pin_files_that_are_not_a_list_are_refused(self) -> None:
        """A string is not a list of paths."""
        extra = '\n[relock]\npin_files = "a"\n'
        message = fakes.error_of(lambda: fakes.settings(fakes.directory(), extra))
        assert_that(message, contains_string("pin_files must be a list"))

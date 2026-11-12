"""T53, T56, T110: the quarantine.

Race and local-run rules and the unchecked phrases.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import brief, phrases
from .briefmake import text as brief_text
from .test_env_check import WORKERS

BANNED = phrases.parse(phrases.default_text(), "default")
REVIEWERS = tuple(
    each for each in brief.Kind if "Quarantine check:" in brief_text(each)
)


def found(text: str) -> list[str]:
    """The phrase findings of a text.

    Args:
        text: the text.

    Returns:
        The findings.
    """
    return list(phrases.findings(text, "t", BANNED))


class TestTheRulesAreInTheBriefs(unittest.TestCase):
    """Each worker brief and each review brief carries the lines."""

    def test_t53_a_worker_brief_has_the_quarantine_and_race_lines(self) -> None:
        """``Quarantine:``, ``Race:``, ``Root cause:``, ``Injection:``, ``CI run:``."""
        for kind in WORKERS:
            printed = brief_text(kind)
            for word in (
                "`Quarantine: ...`",
                "`Race: ...`",
                "`Injection: ...`",
                "`CI run: <URL>`",
            ):
                assert_that(printed, contains_string(word))

    def test_t53_a_review_brief_has_the_check_lines(self) -> None:
        """``Quarantine check:`` and ``Race check:``."""
        assert_that(len(REVIEWERS) > 0, equal_to(True))
        for kind in REVIEWERS:
            assert_that(brief_text(kind), contains_string("`Race check:`"))

    def test_t56_a_worker_brief_says_runs_are_short_and_in_the_foreground(self) -> None:
        """No background run, no sleep loop."""
        for kind in WORKERS:
            assert_that(brief_text(kind), contains_string("no background run"))


class TestThePhrases(unittest.TestCase):
    """Each row refuses its example and passes the text without it."""

    def test_t56_each_background_and_sleep_form_is_refused(self) -> None:
        """``run_in_background``, ``nohup``, ``sleep N``."""
        for said in ("pass run_in_background", "use nohup make", "then sleep 60"):
            with self.subTest(said):
                assert_that(found(f"Do {said} now."), has_length(1))
        assert_that(found("Push and let CI run it."), equal_to([]))

    def test_t110_each_unchecked_form_is_refused_and_removal_passes(self) -> None:
        """The four forms of the owner's correction pattern."""
        for said in (
            "we have not checked it",
            "it is not checked yet",
            "I did not verify that",
        ):
            with self.subTest(said):
                assert_that(found(said), has_length(1))
                assert_that(found("The parser was read and it rejects."), equal_to([]))

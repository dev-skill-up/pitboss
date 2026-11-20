"""The re-run rule: only a flake's re-run is refused (C13, pitboss#444)."""

import ast
import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brieftext, causetext, rerunrule, report, stuckci
from . import queuedrun

STUCK = rerunrule.Run(status="queued", jobs=0)
FLAKE = rerunrule.Run(status="completed", jobs=3)
QUEUED_WITH_JOBS = rerunrule.Run(status="queued", jobs=2)


class TestRerunRule(unittest.TestCase):
    """A flake's re-run is refused; a re-run around a GitHub problem is not."""

    def test_c13_a_run_stuck_queued_with_no_jobs_may_be_rerun(self) -> None:
        """Planted: a queued run with 0 jobs is not refused."""
        assert_that(rerunrule.refusal(STUCK), equal_to(""))

    def test_c13_a_flake_rerun_is_refused(self) -> None:
        """A finished run, and a queued one that has jobs, are refused."""
        said = [rerunrule.refusal(each) for each in (FLAKE, QUEUED_WITH_JOBS)]
        for each in said:
            assert_that(each, contains_string("get rid of a flake is refused"))

    def test_c13_no_text_forbids_a_rerun_for_a_github_problem(self) -> None:
        """The rule's wording names the flake, and allows the GitHub problem."""
        for each in ("get rid of a flake is refused", "stuck queued with no jobs"):
            assert_that(causetext.RULE, contains_string(each))
        wording = [causetext.RULE, brieftext.LOCAL, report.HOLD_ACTIONS]
        found = ["never re-run CI" in each for each in wording]
        assert_that(found, equal_to([False] * 3))

    def test_c13_the_step_allows_the_stuck_rerun_and_refuses_the_flake(self) -> None:
        """``step`` is the refusal for a flake and the allowance otherwise."""
        assert_that(rerunrule.step(FLAKE), equal_to(rerunrule.refusal(FLAKE)))
        for words in ("re-run it", "no flake"):
            assert_that(rerunrule.step(STUCK), contains_string(words))

    def test_c13_the_stuck_warning_is_the_rerun_rules_step(self) -> None:
        """The production caller: the warning of a queued run says ``step``."""
        text = stuckci.warning("o/r", 7, "a" * 40, (queuedrun.RUN, 90, 2))
        assert_that(text, contains_string(rerunrule.step(STUCK)))
        assert_that("no re-run" in text, equal_to(False))

    def test_c13_no_printed_string_forbids_a_rerun_outright(self) -> None:
        """Every string of the program that holds ``re-run`` is read."""
        forbidding = ("no re-run", "never re-run", "not re-run", "no rerun")
        found: list[tuple[str, str]] = []
        for path in sorted(pathlib.Path(__file__).parents[1].glob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    text = node.value.lower()
                    if "re-run" in text or "rerun" in text:
                        found.extend((path.name, w) for w in forbidding if w in text)
        assert_that(found, equal_to([]))

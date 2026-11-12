"""The re-run rule: only a flake's re-run is refused (C13, pitboss#444)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brieftext, causetext, rerunrule, report

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
        assert_that(causetext.RULE, contains_string("get rid of a flake is refused"))
        assert_that(causetext.RULE, contains_string("stuck queued with no jobs"))
        wording = [causetext.RULE, brieftext.LOCAL, report.HOLD_ACTIONS]
        assert_that(
            ["never re-run CI" in each for each in wording], equal_to([False] * 3)
        )

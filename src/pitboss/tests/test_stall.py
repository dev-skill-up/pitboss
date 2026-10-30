"""Tests for the STALL line: a relock PR whose check stays red over four hours."""

import dataclasses
import datetime
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import config, parsing, pulls, reviews, shapes, stall
from . import fakes, world
from .test_commands import sweep

NOW = datetime.datetime(2026, 10, 30, 12, 0, 0, tzinfo=datetime.timezone.utc)
RELOCK = "relock/2026-10-30"


def completed(seconds_ago: int) -> str:
    """The completed_at of a run that completed a number of seconds before NOW.

    Args:
        seconds_ago: how long before the fixed clock.

    Returns:
        The ISO 8601 time.
    """
    return (NOW - datetime.timedelta(seconds=seconds_ago)).isoformat()


def check(
    seconds_ago: int, failed: bool = True, name: str = "check", identifier: int = 8
) -> shapes.CheckRun:
    """A completed check run.

    Args:
        seconds_ago: how long before NOW it completed.
        failed: whether it failed.
        name: its name.
        identifier: its id.

    Returns:
        The check run.
    """
    return shapes.CheckRun(
        id=identifier,
        name=name,
        finished=True,
        failed=failed,
        completed_at=completed(seconds_ago),
    )


def facts(branch: str, checks: Sequence[shapes.CheckRun]) -> pulls.PullFacts:
    """A PR on a branch with check runs.

    Args:
        branch: its head branch.
        checks: its head's check runs.

    Returns:
        The PR.
    """
    head = {"sha": fakes.HEAD, "ref": branch}
    body = fakes.pull_body(7, head=head)
    return pulls.PullFacts(
        repo=config.Repo(owner="o", name="r", slug="o/r"),
        pull=parsing.pull(json.dumps(body)),
        checks=checks,
        review=None,
        standing=reviews.Standing.NONE,
    )


def printed(pull: pulls.PullFacts) -> Sequence[str]:
    """The STALL lines of a PR at the fixed clock.

    Args:
        pull: the PR.

    Returns:
        The lines.
    """
    return stall.lines(pull, NOW, {8: ["Run bats check", "Run tests"]})


class TestStall(unittest.TestCase):
    """The four hours, from the run's completed_at."""

    def test_red_over_four_hours_stalls(self) -> None:
        """One second over four hours prints STALL with the time and the steps."""
        [line] = printed(facts(RELOCK, [check(14401)]))
        assert_that(line, contains_string("STALL o/r#7: relock check red for 4h00m01s"))
        assert_that(line, contains_string("(14401 seconds, over 14400)"))
        assert_that(line, contains_string("check (job 8): Run bats check, Run tests;"))
        assert_that(line, contains_string("fix it before the other fixes"))

    def test_red_for_four_hours_or_less_is_quiet(self) -> None:
        """One second short of four hours, and exactly 14400 seconds, print nothing."""
        for seconds in (14399, 14400):
            with self.subTest(seconds):
                assert_that(printed(facts(RELOCK, [check(seconds)])), equal_to([]))

    def test_a_pr_that_is_not_a_relock_is_quiet(self) -> None:
        """Any other branch, red for a day, prints nothing."""
        for branch in ("fix-29", "relocking/x", "not/relock/x"):
            with self.subTest(branch):
                assert_that(printed(facts(branch, [check(86400)])), equal_to([]))

    def test_a_stalled_relock_draft_still_stalls(self) -> None:
        """A draft is not excluded: a red relock draft over four hours prints STALL."""
        head = {"sha": fakes.HEAD, "ref": RELOCK}
        body = fakes.pull_body(7, head=head, draft=True)
        draft = dataclasses.replace(
            facts(RELOCK, [check(14401)]), pull=parsing.pull(json.dumps(body))
        )
        assert_that(draft.pull.draft, equal_to(True))
        assert_that(len(printed(draft)), equal_to(1))

    def test_a_green_relock_pr_is_quiet(self) -> None:
        """A relock PR whose check passed prints nothing, however old."""
        assert_that(printed(facts(RELOCK, [check(86400, failed=False)])), equal_to([]))

    def test_only_the_required_check_counts(self) -> None:
        """A red job that is not the required check does not stall by itself."""
        pull = facts(RELOCK, [check(86400, name="static")])
        assert_that(printed(pull), equal_to([]))

    def test_the_callers_check_name_is_the_required_check(self) -> None:
        """A library's required check is shown as ``check / check``."""
        pull = facts(RELOCK, [check(20000, name="check / check")])
        assert_that(len(printed(pull)), equal_to(1))

    def test_every_failing_job_is_named_with_its_steps(self) -> None:
        """The required check and another failed job are both listed."""
        other = check(20000, name="static", identifier=9)
        pull = facts(RELOCK, [check(20000), other])
        [line] = stall.lines(pull, NOW, {8: ["a"], 9: []})
        assert_that(line, contains_string("check (job 8): a; static (job 9): "))
        assert_that(line, contains_string("no failed step read"))

    def test_a_run_with_no_completion_time_is_quiet(self) -> None:
        """Without a completed_at there is nothing to count from."""
        run = shapes.CheckRun(id=8, name="check", finished=True, failed=True)
        assert_that(printed(facts(RELOCK, [run])), equal_to([]))

    def test_the_longest_red_required_run_counts(self) -> None:
        """With two required runs red, the older completion is used."""
        runs = [check(100), check(20000, name="check / check", identifier=9)]
        assert_that(stall.red_seconds(facts(RELOCK, runs), NOW), equal_to(20000))


class TestSweepPrintsStall(unittest.TestCase):
    """``pitboss sweep`` prints the line, with the failed steps read from GitHub."""

    def test_sweep_prints_stall_for_a_stalled_relock_pr(self) -> None:
        """PR 1 on a relock branch, its check red 14 hours before the sweep."""
        here = world.make_world()
        details = fakes.pull_body(
            1, head={"sha": "1" * 40, "ref": RELOCK}, mergeable_state="blocked"
        )
        red = dict(world.RED, name="check", completed_at="2029-12-31T10:00:00+00:00")
        here.bodies["repos/owner/project/pulls/1"] = details
        here.bodies[
            fakes.page(f"repos/owner/project/commits/{'1' * 40}/check-runs")
        ] = {"check_runs": [red]}
        swept = sweep(here)
        [line] = [x for x in swept.out.splitlines() if x.startswith("STALL")]
        assert_that(
            line,
            contains_string(
                "STALL owner/project#1: relock check red for 14h00m00s"
                " (50400 seconds, over 14400); failing steps:"
                " check (job 8): Run bats check;"
            ),
        )

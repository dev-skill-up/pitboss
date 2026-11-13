"""A failed commit status is read, and decides the PR's step (#162).

The cause: a commit status that failed (``text-lint``) was never read. A PR whose
step is a wait has no decision and nothing is said of it (keyword: one-path).
"""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, test_flow_sweep, world
from .pinsworld import offered as third_of
from .test_commands import sweep

HEAD = test_flow_sweep.HEAD
PATHS = {
    kind: fakes.page(f"{world.PROJECT}/commits/{HEAD}/{kind}")
    for kind in ("status", "check-runs")
}
RUN = "https://github.com/owner/project/actions/runs/5"
REVIEW = "REVIEWER: owner/project#3: grade the Plan ONLY"
# keyword: finish-partial: a red text-lint status on a PR to review is finished first
FINISH = (
    "WORKER: owner/project#3: finish this PR, handed back unfinished: the"
    " `text-lint` status of the head is red ({}): fix the body"
)
PASSED = {
    "id": 9,
    "name": "text-lint",
    "status": "completed",
    "conclusion": "success",
    "completed_at": "2026-10-31T00:00:00Z",
}
WAITING = {"id": 9, "name": "t", "status": "in_progress", "conclusion": None}


def status(
    state: str, description: str = "", context: str = "text-lint"
) -> Mapping[str, str]:
    """One commit status as the API gives it.

    Args:
        state: its state.
        description: its description.
        context: its context.

    Returns:
        The JSON.
    """
    return {
        "context": context,
        "state": state,
        "description": description,
        "target_url": RUN,
        "created_at": "2026-10-30T00:00:00Z",
    }


def with_statuses(
    statuses: Sequence[Mapping[str, str]], **changes: object
) -> world.World:
    """A world whose PR 3 has the commit statuses.

    Args:
        statuses: the statuses of PR 3's head.
        **changes: changes to PR 3's JSON.

    Returns:
        The world.
    """
    here = test_flow_sweep.world_with([], **changes)
    here.bodies[PATHS["status"]] = {"statuses": list(statuses)}
    return here


class TestAFailedStatus(unittest.TestCase):
    """A PR with a failing ``text-lint`` status and no review (Done-when 2)."""

    def test_the_decision_names_the_status_and_its_description(self) -> None:
        """The worker finishes the body; the description is quoted."""
        here = with_statuses([status("failure", "first-line")], draft=True)
        assert_that(third_of(here), contains_string(FINISH.format("first-line")))

    def test_the_sweep_decides_the_same(self) -> None:
        """The same decision, in the sweep's lines."""
        here = with_statuses([status("failure")], draft=True)
        assert_that(sweep(here).out, contains_string(FINISH.format("failure")))

    def test_only_a_failure_or_an_error_decides_it(self) -> None:
        """A passing or a pending status leaves the review."""
        found = {
            state: FINISH.format(state) in third_of(with_statuses([status(state)]))
            for state in ("success", "pending", "failure", "error")
        }
        wanted = {"success": False, "pending": False, "failure": True, "error": True}
        assert_that(found, equal_to(wanted))

    def test_another_context_is_not_the_body(self) -> None:
        """Only text-lint is the body's: another context leaves the review."""
        here = with_statuses([status("failure", context="other")], draft=True)
        assert_that(third_of(here), contains_string(REVIEW))


class TestDecisions(unittest.TestCase):
    """Done-when 1: a PR's step is its decision, or it has none."""

    def test_a_head_waiting_for_ci_has_no_decision(self) -> None:
        """A running check: PR 3 waits, so it is in no answer."""
        here = test_flow_sweep.world_with([])
        here.bodies[PATHS["check-runs"]] = {"check_runs": [WAITING]}
        assert_that(third_of(here), equal_to(""))

    def test_a_pr_offered_for_a_round_names_the_round(self) -> None:
        """The words of its decision."""
        found = third_of(world.make_world())
        assert_that(found, contains_string("REVIEWER: owner/project#3: "))


class TestAnsweredStatus(unittest.TestCase):
    """A failed status that a later passing check run of its name answers."""

    def test_a_later_passing_check_run_clears_it(self) -> None:
        """The newest answer is the pass: the review again."""
        here = with_statuses([status("failure")], draft=True)
        here.bodies[PATHS["check-runs"]] = {"check_runs": [PASSED]}
        assert_that(third_of(here), contains_string(REVIEW))

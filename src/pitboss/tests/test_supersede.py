"""Tests for a failed check run that a newer passing status answers (#136)."""

import dataclasses
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_exactly, equal_to, has_item

from .. import parsing, shapes, supersede
from . import fakes, world
from .test_commands import sweep

FAILED_AT = "2026-11-02T21:01:47Z"
LATER = "2026-11-03T01:06:05Z"
EARLIER = "2026-11-02T20:00:00Z"
RUN = 41524542678
OTHER_RUN = 41524542999
WORKFLOW = ".github/workflows/text-lint.yml"
FAILED_LINE = "FAILED owner/project#1: lint"
HEAD = "1" * 40
RUN_URL = f"repos/owner/project/actions/runs/{RUN}"
OTHER_URL = f"repos/owner/project/actions/runs/{OTHER_RUN}"


def check(name: str = "lint", run: int = RUN) -> shapes.CheckRun:
    """The failed check run of the ticket: job ``lint`` of a workflow's run.

    Args:
        name: its name.
        run: its Actions run.

    Returns:
        The check run.
    """
    return shapes.CheckRun(
        id=125548778441,
        name=name,
        finished=True,
        failed=True,
        completed_at=FAILED_AT,
        run=run,
    )


def status(
    context: str = "text-lint",
    created: str = LATER,
    run: int = RUN,
    succeeded: bool = True,
) -> shapes.CommitStatus:
    """The commit status the workflow posts.

    Args:
        context: its context.
        created: when it was posted.
        run: the run its target URL names.
        succeeded: whether it is ``success``.

    Returns:
        The status.
    """
    return shapes.CommitStatus(
        context=context,
        succeeded=succeeded,
        created_at=created,
        run=run,
        state="success" if succeeded else "failure",
        url=f"https://github.com/o/r/actions/runs/{run}" if run else "",
    )


def failed(
    checks: Sequence[shapes.CheckRun],
    posted: Sequence[shapes.CommitStatus],
    lookup: Mapping[int, str],
) -> Sequence[bool]:
    """Whether each check is still failed after the statuses are read.

    Args:
        checks: the check runs.
        posted: the statuses.
        lookup: the workflow file of each run (a run not in it is not asked).

    Returns:
        The ``failed`` of each check.
    """
    settled = supersede.settle(checks, posted, lookup.__getitem__)
    return [each.failed for each in settled]


class TestSettle(unittest.TestCase):
    """The newest of the check run and the status decides."""

    def test_older_failure_and_newer_pass_of_one_name_is_not_failed(self) -> None:
        """A check run that failed before a passing status of its name."""
        assert_that(failed([check("lint")], [status("lint")], {}), equal_to([False]))

    def test_newer_failure_and_older_pass_of_one_name_is_failed(self) -> None:
        """A check run that failed after the passing status of its name."""
        older = status("lint", created=EARLIER)
        assert_that(failed([check("lint")], [older], {}), equal_to([True]))

    def test_a_status_at_the_same_second_does_not_clear(self) -> None:
        """Only a later status answers (the failure wins a tie)."""
        same = status("lint", created=FAILED_AT)
        assert_that(failed([check("lint")], [same], {}), equal_to([True]))

    def test_a_newer_failing_or_pending_status_does_not_clear(self) -> None:
        """A status that did not succeed leaves the failure standing."""
        red = status("lint", succeeded=False)
        assert_that(failed([check("lint")], [red], {}), equal_to([True]))

    def test_the_tickets_names_differ_and_the_run_is_one(self) -> None:
        """Job ``lint`` and context ``text-lint`` of one run (no lookup)."""
        assert_that(failed([check()], [status()], {}), equal_to([False]))

    def test_another_run_of_the_same_workflow_answers(self) -> None:
        """A status of a later run of the workflow that ran the check."""
        lookup = {RUN: WORKFLOW, OTHER_RUN: WORKFLOW}
        assert_that(
            failed([check()], [status(run=OTHER_RUN)], lookup), equal_to([False])
        )

    def test_a_status_of_another_workflow_does_not_answer(self) -> None:
        """Names differ and the workflows do too: the failure stands."""
        lookup = {RUN: WORKFLOW, OTHER_RUN: ".github/workflows/other.yml"}
        assert_that(
            failed([check()], [status(run=OTHER_RUN)], lookup), equal_to([True])
        )

    def test_a_status_with_no_run_and_another_name_does_not_answer(self) -> None:
        """Nothing links them."""
        assert_that(failed([check()], [status(run=0)], {}), equal_to([True]))

    def test_a_check_with_no_run_and_another_name_is_not_answered(self) -> None:
        """A check run that is not an Actions one has no workflow to compare."""
        assert_that(failed([check(run=0)], [status()], {}), equal_to([True]))

    def test_a_passing_check_is_left_alone(self) -> None:
        """Only failures are looked at."""
        ok = dataclasses.replace(check("lint"), failed=False)
        assert_that(failed([ok], [status("lint")], {}), equal_to([False]))


class TestParsing(unittest.TestCase):
    """The shapes read out of GitHub's answers."""

    def test_the_run_of_a_url(self) -> None:
        """A job URL, a run URL and no run."""
        base = "https://github.com/o/r/actions/runs/7"
        assert_that(parsing.run_of(f"{base}/job/9"), equal_to(7))
        assert_that(parsing.run_of(base), equal_to(7))
        assert_that(parsing.run_of("https://example.org/x"), equal_to(0))
        assert_that(parsing.run_of(None), equal_to(0))

    def test_statuses(self) -> None:
        """The newest status of a context, with the run its target names."""
        body = (
            '{"statuses": [{"context": "text-lint", "state": "success",'
            ' "created_at": "2026-11-03T01:06:05Z",'
            ' "target_url": "https://github.com/o/r/actions/runs/41524542678"},'
            ' {"context": "x", "state": "pending", "created_at": null,'
            ' "target_url": null}]}'
        )
        found = parsing.statuses(body)
        assert_that(
            found,
            contains_exactly(
                status("text-lint", created="2026-11-03T01:06:05Z", run=41524542678),
                shapes.CommitStatus(
                    context="x", succeeded=False, created_at="", state="pending"
                ),
            ),
        )

    def test_the_path_of_a_run(self) -> None:
        """A run's workflow file, and none."""
        assert_that(parsing.run_path('{"path": "a.yml"}'), equal_to("a.yml"))
        assert_that(parsing.run_path("{}"), equal_to(""))


FAILED_RUN = {
    "id": 125548778441,
    "name": "lint",
    "status": "completed",
    "conclusion": "failure",
    "head_sha": HEAD,
    "started_at": "2026-11-02T21:01:41Z",
    "completed_at": FAILED_AT,
    "details_url": f"https://github.com/owner/project/actions/runs/{RUN}/job/1",
}


def ticket_world(
    posted: Sequence[Mapping[str, object]], extra: Mapping[str, object] | None = None
) -> world.World:
    """A world whose PR 1 has the ticket's failed ``lint`` and these statuses.

    Args:
        posted: the head's statuses.
        extra: more canned bodies.

    Returns:
        The world.
    """
    here = world.make_world()
    path = f"repos/owner/project/commits/{HEAD}"
    pages = [
        ("check-runs", {"check_runs": [FAILED_RUN]}),
        ("status", {"statuses": posted}),
    ]
    here.bodies.update(fakes.bodies_under(path, pages))
    here.bodies.update(extra or {})
    return here


def posted_status(created: str, state: str = "success") -> Mapping[str, object]:
    """The ``text-lint`` status of the ticket's head, as GitHub gives it.

    Args:
        created: its created_at.
        state: its state.

    Returns:
        The JSON.
    """
    return {
        "context": "text-lint",
        "state": state,
        "created_at": created,
        "target_url": f"https://github.com/owner/project/actions/runs/{OTHER_RUN}",
    }


def lines_of(here: world.World) -> Sequence[str]:
    """The lines of a sweep.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    return sweep(here).out.splitlines()


class TestSweepOfTheTicketsHead(unittest.TestCase):
    """bats-lang/quire#1032: job ``lint`` failed, status ``text-lint`` passed later."""

    def test_no_failed_line_when_the_status_is_later(self) -> None:
        """The status came after the failure, from a run of the same workflow."""
        here = ticket_world(
            [posted_status(LATER)],
            {RUN_URL: {"path": WORKFLOW}, OTHER_URL: {"path": WORKFLOW}},
        )
        assert_that(FAILED_LINE in lines_of(here), equal_to(False))

    def test_a_failed_line_when_the_status_is_older(self) -> None:
        """The failure is the newest of the two (the reverse)."""
        here = ticket_world(
            [posted_status(EARLIER)],
            {RUN_URL: {"path": WORKFLOW}, OTHER_URL: {"path": WORKFLOW}},
        )
        assert_that(lines_of(here), has_item(FAILED_LINE))

    def test_a_failed_line_when_the_status_failed(self) -> None:
        """A later status that is red does not clear the red check run."""
        here = ticket_world([posted_status(LATER, "failure")])
        assert_that(lines_of(here), has_item(FAILED_LINE))

    def test_an_unreadable_status_is_said(self) -> None:
        """No status answer is the PR unreadable, not a silent FAILED."""
        here = ticket_world([])
        del here.bodies[fakes.page(f"repos/owner/project/commits/{HEAD}/status")]
        lines = lines_of(here)
        assert_that(FAILED_LINE in lines, equal_to(False))
        assert_that(
            lines, has_item("UNREADABLE owner/project#1: status answered HTTP 404")
        )

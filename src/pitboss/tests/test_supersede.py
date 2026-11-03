"""Tests for a failed check run that a newer passing status answers (#136)."""

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
HEAD = "1" * 40
RUNS = f"repos/owner/project/actions/runs/{RUN}"
OTHER_RUNS = f"repos/owner/project/actions/runs/{OTHER_RUN}"


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
        context=context, succeeded=succeeded, created_at=created, run=run
    )


def workflows(found: Mapping[int, str]) -> "Lookup":
    """A workflow lookup that answers from a table.

    Args:
        found: the workflow file of each run id.

    Returns:
        The lookup.
    """
    return Lookup(found)


class Lookup:
    """Answers the workflow file of a run, and remembers what was asked."""

    def __init__(self, found: Mapping[int, str]) -> None:
        """Keep the table.

        Args:
            found: the workflow file of each run id.
        """
        self.found = found
        self.asked: list[int] = []

    def __call__(self, run: int) -> str:
        """Answer one run.

        Args:
            run: its id.

        Returns:
            Its workflow file.
        """
        self.asked.append(run)
        return self.found[run]


def failed(
    checks: Sequence[shapes.CheckRun],
    posted: Sequence[shapes.CommitStatus],
    lookup: Lookup | None = None,
) -> Sequence[bool]:
    """Whether each check is still failed after the statuses are read.

    Args:
        checks: the check runs.
        posted: the statuses.
        lookup: the workflow lookup (none asked for by default).

    Returns:
        The ``failed`` of each check.
    """
    settled = supersede.settle(checks, posted, lookup or workflows({}))
    return [each.failed for each in settled]


class TestSettle(unittest.TestCase):
    """The newest of the check run and the status decides."""

    def test_older_failure_and_newer_pass_of_one_name_is_not_failed(self) -> None:
        """A check run that failed before a passing status of its name."""
        assert_that(failed([check("lint")], [status("lint")]), equal_to([False]))

    def test_newer_failure_and_older_pass_of_one_name_is_failed(self) -> None:
        """A check run that failed after the passing status of its name."""
        older = status("lint", created=EARLIER)
        assert_that(failed([check("lint")], [older]), equal_to([True]))

    def test_a_status_at_the_same_second_does_not_clear(self) -> None:
        """Only a later status answers (the failure wins a tie)."""
        same = status("lint", created=FAILED_AT)
        assert_that(failed([check("lint")], [same]), equal_to([True]))

    def test_a_newer_failing_or_pending_status_does_not_clear(self) -> None:
        """A status that did not succeed leaves the failure standing."""
        red = status("lint", succeeded=False)
        assert_that(failed([check("lint")], [red]), equal_to([True]))

    def test_the_tickets_names_differ_and_the_run_is_one(self) -> None:
        """Job ``lint`` and context ``text-lint`` of one run (no lookup)."""
        lookup = workflows({})
        assert_that(failed([check()], [status()], lookup), equal_to([False]))
        assert_that(lookup.asked, equal_to([]))

    def test_another_run_of_the_same_workflow_answers(self) -> None:
        """A status of a later run of the workflow that ran the check."""
        lookup = workflows({RUN: WORKFLOW, OTHER_RUN: WORKFLOW})
        assert_that(
            failed([check()], [status(run=OTHER_RUN)], lookup), equal_to([False])
        )

    def test_a_status_of_another_workflow_does_not_answer(self) -> None:
        """Names differ and the workflows do too: the failure stands."""
        lookup = workflows({RUN: WORKFLOW, OTHER_RUN: ".github/workflows/other.yml"})
        assert_that(
            failed([check()], [status(run=OTHER_RUN)], lookup), equal_to([True])
        )

    def test_a_status_with_no_run_and_another_name_does_not_answer(self) -> None:
        """Nothing links them."""
        assert_that(failed([check()], [status(run=0)]), equal_to([True]))

    def test_a_check_with_no_run_and_another_name_is_not_answered(self) -> None:
        """A check run that is not an Actions one has no workflow to compare."""
        assert_that(failed([check(run=0)], [status()]), equal_to([True]))

    def test_a_passing_check_is_left_alone(self) -> None:
        """Only failures are looked at."""
        ok = shapes.CheckRun(id=1, name="lint", finished=True, failed=False)
        assert_that(failed([ok], [status("lint")]), equal_to([False]))


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
                status("text-lint"),
                shapes.CommitStatus(context="x", succeeded=False, created_at=""),
            ),
        )

    def test_the_path_of_a_run(self) -> None:
        """A run's workflow file, and none."""
        assert_that(parsing.run_path('{"path": "a.yml"}'), equal_to("a.yml"))
        assert_that(parsing.run_path("{}"), equal_to(""))


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
    run = {
        "id": 125548778441,
        "name": "lint",
        "status": "completed",
        "conclusion": "failure",
        "head_sha": HEAD,
        "started_at": "2026-11-02T21:01:41Z",
        "completed_at": FAILED_AT,
        "details_url": f"https://github.com/owner/project/actions/runs/{RUN}/job/1",
    }
    path = f"repos/owner/project/commits/{HEAD}"
    here.bodies[fakes.page(f"{path}/check-runs")] = {"check_runs": [run]}
    here.bodies[fakes.page(f"{path}/status")] = {"statuses": list(posted)}
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


def failed_lines(here: world.World) -> Sequence[str]:
    """The FAILED lines of PR 1 in a sweep.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    return [x for x in sweep(here).out.splitlines() if x.startswith("FAILED")]


class TestSweepOfTheTicketsHead(unittest.TestCase):
    """bats-lang/quire#1032: job ``lint`` failed, status ``text-lint`` passed later."""

    def test_no_failed_line_when_the_status_is_later(self) -> None:
        """The status came after the failure, from a run of the same workflow."""
        here = ticket_world(
            [posted_status(LATER)],
            {RUNS: {"path": WORKFLOW}, OTHER_RUNS: {"path": WORKFLOW}},
        )
        lines = failed_lines(here)
        assert_that([x for x in lines if "#1:" in x], equal_to([]))

    def test_a_failed_line_when_the_status_is_older(self) -> None:
        """The failure is the newest of the two (the reverse)."""
        here = ticket_world(
            [posted_status(EARLIER)],
            {RUNS: {"path": WORKFLOW}, OTHER_RUNS: {"path": WORKFLOW}},
        )
        assert_that(
            failed_lines(here),
            has_item("FAILED owner/project#1: lint"),
        )

    def test_a_failed_line_when_the_status_failed(self) -> None:
        """A later status that is red does not clear the red check run."""
        here = ticket_world([posted_status(LATER, "failure")])
        assert_that(failed_lines(here), has_item("FAILED owner/project#1: lint"))

    def test_an_unreadable_status_is_said(self) -> None:
        """No status answer is the PR unreadable, not a silent FAILED."""
        here = ticket_world([])
        del here.bodies[fakes.page(f"repos/owner/project/commits/{HEAD}/status")]
        lines = sweep(here).out.splitlines()
        assert_that("FAILED owner/project#1: lint" in lines, equal_to(False))
        assert_that(
            lines, has_item("UNREADABLE owner/project#1: status answered HTTP 404")
        )

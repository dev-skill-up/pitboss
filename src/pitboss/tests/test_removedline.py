"""Tests for the REMOVED FROM QUEUE line (keyword: removed-from-queue, pitboss#138).

The fixtures are the case of bats-lang/quire#1032: the queue added the PR at
22:44:11 and removed it at 23:28:52, and a job of the group's run had failed.
"""

import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import config, parsing, pulls, queue, removedline, reviews, shapes
from . import fakes, test_work, world
from .test_commands import sweep

ADDED = {"event": "added_to_merge_queue", "created_at": "2029-12-31T22:44:11Z"}
REMOVED = {"event": "removed_from_merge_queue", "created_at": "2029-12-31T23:28:52Z"}
ADDED_AGAIN = {"event": "added_to_merge_queue", "created_at": "2029-12-31T23:40:00Z"}
LABELED = {"event": "labeled", "created_at": "2029-12-31T20:00:00Z"}
COMMITTED = {"event": "committed"}
QUEUE_BRANCH = "gh-readonly-queue/main/pr-2-"
TIMELINE = fakes.page(f"{world.PROJECT}/issues/2/timeline")
MERGE_QUEUE = "\n[merge_queue]\nrepositories = ['project']\n"
REMOVED_LINE = "REMOVED FROM QUEUE owner/project#2: 2029-12-31T23:28:52Z, "
FAILED_TEXT = (
    "failed job of its last queue run: android / build-android: Fetch dependencies"
)
READY_LINE = "READY TO MERGE owner/project#2: arm auto-merge"
STANDARD_LINE = READY_LINE + " or merge"
FAILED_JOB = {
    "name": "android / build-android",
    "conclusion": "failure",
    "steps": [
        {"name": "Set up job", "conclusion": "success"},
        {"name": "Fetch dependencies", "conclusion": "failure"},
    ],
}
PASSED_JOB = {"name": "check / check", "conclusion": "success", "steps": []}
CANCELLED_JOB = {"name": "android / build-android", "conclusion": "cancelled"}
BARE_FAILED_JOB = {"name": "check / test", "conclusion": "failure"}


def _run(identifier: int, branch: str, minute: int) -> dict[str, object]:
    return {
        "id": identifier,
        "status": "completed",
        "conclusion": "failure",
        "created_at": f"2029-12-31T23:{minute:02d}:00+00:00",
        "head_branch": QUEUE_BRANCH + branch,
    }


def removed_world(
    events: Sequence[object],
    jobs: Sequence[object],
    extra: str = MERGE_QUEUE,
) -> world.World:
    """A world whose approved, green, clean PR 2 has a queue timeline and runs.

    Args:
        events: the timeline of PR 2.
        jobs: the jobs of its last group's first run.
        extra: more TOML appended to the configuration.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies[TIMELINE] = list(events)
    here.bodies[fakes.page(f"{world.PROJECT}/issues/1/timeline")] = []
    here.bodies[fakes.page(f"{world.PROJECT}/issues/3/timeline")] = []
    here.bodies[fakes.page(f"{world.PROJECT}/actions/runs?event=merge_group")] = {
        "workflow_runs": [
            _run(11, "old", 10),
            _run(12, "new", 28),
            _run(13, "new", 29),
        ]
    }
    here.bodies[fakes.page(f"{world.PROJECT}/actions/runs/12/jobs")] = {"jobs": jobs}
    here.bodies[fakes.page(f"{world.PROJECT}/actions/runs/13/jobs")] = {
        "jobs": [PASSED_JOB]
    }
    fakes.settings(here.workspace, world.EXTRA.format(ledger=here.ledger) + extra)
    return here


def lines_of(here: world.World) -> Sequence[str]:
    """The sweep's lines about PR 2 of the project.

    Args:
        here: the world.

    Returns:
        The lines that start with a marker and name the PR, without its summary.
    """
    return [
        line
        for line in sweep(here).out.splitlines()
        if "owner/project#2" in line and not line.startswith("owner/project#2 [")
    ]


class TestSweep(unittest.TestCase):
    """``pitboss sweep`` on a PR the queue removed."""

    def test_removal_with_a_failed_job(self) -> None:
        """The line names the time, the failed job and its step, then READY."""
        here = removed_world([LABELED, ADDED, REMOVED], [PASSED_JOB, FAILED_JOB])
        found = lines_of(here)
        assert_that(found, equal_to([REMOVED_LINE + FAILED_TEXT, READY_LINE]))

    def test_removal_with_no_failed_job_is_cancelled_by_the_queue(self) -> None:
        """No job failed in the run: it says cancelled by the queue."""
        here = removed_world([ADDED, REMOVED], [PASSED_JOB, CANCELLED_JOB])
        expected = REMOVED_LINE + (
            "no failed job in its last queue run: cancelled by the queue"
        )
        assert_that(lines_of(here), equal_to([expected, READY_LINE]))

    def test_a_failed_job_with_no_failed_step(self) -> None:
        """A failed job whose steps were not read says so."""
        here = removed_world([ADDED, REMOVED], [BARE_FAILED_JOB])
        expected = REMOVED_LINE + (
            "failed job of its last queue run: check / test: no failed step read"
        )
        assert_that(lines_of(here), equal_to([expected, READY_LINE]))

    def test_the_removal_is_found_on_a_later_page(self) -> None:
        """A timeline of more than a page is read to its end."""
        first = [LABELED] * 99 + [ADDED]
        here = removed_world(first, [FAILED_JOB])
        here.bodies[fakes.page(f"{world.PROJECT}/issues/2/timeline", 2)] = [REMOVED]
        assert_that(lines_of(here)[0], equal_to(REMOVED_LINE + FAILED_TEXT))

    def test_queued_again_prints_no_removal(self) -> None:
        """A PR added to the queue after its removal is in the queue again."""
        here = removed_world([ADDED, REMOVED, ADDED_AGAIN], [FAILED_JOB])
        assert_that(lines_of(here), equal_to([STANDARD_LINE]))

    def test_other_timelines_print_none(self) -> None:
        """Never queued, removed with no addition and added only: no removal."""
        found = [
            [e for e in lines_of(removed_world(events, [FAILED_JOB])) if "REMOVED" in e]
            for events in ([], [COMMITTED, LABELED], [REMOVED], [ADDED])
        ]
        assert_that(found, equal_to([[], [], [], []]))

    def test_a_repository_without_a_queue_reads_no_timeline(self) -> None:
        """Outside ``[merge_queue] repositories`` the timeline is not asked for."""
        here = removed_world([ADDED, REMOVED], [FAILED_JOB], extra="")
        called = any("timeline" in " ".join(call) for call in here.calls)
        assert_that((lines_of(here), called), equal_to(([STANDARD_LINE], False)))

    def test_auto_merge_on_prints_no_removal(self) -> None:
        """A PR armed again after the removal has nothing to say."""
        here = removed_world([ADDED, REMOVED], [FAILED_JOB])
        details = fakes.pull_body(2, head={"sha": fakes.HEAD, "ref": "branch-2"})
        details["auto_merge"] = {"enabled_by": {"login": "x"}}
        here.bodies[f"{world.PROJECT}/pulls/2"] = details
        assert_that(lines_of(here), equal_to([]))

    def test_an_unreadable_timeline_is_said(self) -> None:
        """A failing timeline call is an UNREADABLE line, not silence."""
        here = removed_world([ADDED, REMOVED], [FAILED_JOB])
        del here.bodies[TIMELINE]
        expected = "UNREADABLE owner/project#2: timeline answered HTTP 404"
        assert_that(expected in lines_of(here), equal_to(True))

    def test_an_unreadable_job_list_is_said(self) -> None:
        """A failing jobs call is an UNREADABLE line naming the call."""
        here = removed_world([ADDED, REMOVED], [FAILED_JOB])
        del here.bodies[fakes.page(f"{world.PROJECT}/actions/runs/12/jobs")]
        expected = "UNREADABLE owner/project#2: jobs answered HTTP 404"
        assert_that(lines_of(here), equal_to([expected, STANDARD_LINE]))


def facts(**changes: object) -> pulls.PullFacts:
    """An open, green, approved PR of the project.

    Args:
        **changes: fields of the PR's JSON to replace.

    Returns:
        The PR.
    """
    return test_work.facts(2, reviews.Standing.APPROVED, **changes)


class TestUnits(unittest.TestCase):
    """The pieces alone."""

    def test_no_queue_run_read(self) -> None:
        """With no run of the PR among those read, the line says so."""
        pull = facts()
        removal = removedline.Removal(at="T", runs=0, failed=[])
        found = removedline.lines(pull, removal)
        expected = [
            f"REMOVED FROM QUEUE owner/project#2: T, {removedline.NOT_READ}",
            READY_LINE,
        ]
        assert_that(found, equal_to(expected))

    def test_no_group_without_runs(self) -> None:
        """A PR with no queue run among those read has no last group."""
        other = queue.QueueRun(
            repo=config.make_repo("owner", "project"),
            run=shapes.WorkflowRun(
                id=1,
                status="completed",
                conclusion="success",
                finished=True,
                created_at="2029-12-31T23:00:00+00:00",
                head_branch=QUEUE_BRANCH + "x",
            ),
            number=9,
        )
        assert_that(removedline.last_group([other], facts()), equal_to([]))

    def test_a_draft_or_a_conflict_gets_only_the_removal(self) -> None:
        """READY TO MERGE is not asked of a draft or a dirty PR."""
        removal = removedline.Removal(at="T", runs=1, failed=[])
        found = [
            len(removedline.lines(facts(**change), removal))
            for change in ({"draft": True}, {"mergeable_state": "dirty"}, {})
        ]
        assert_that(found, equal_to([1, 1, 2]))

    def test_events_of_other_kinds_are_kept_for_paging(self) -> None:
        """The parser keeps every event, so a full page of them pages on."""
        text = json.dumps([LABELED, COMMITTED])
        found: Mapping[str, str] = {
            event.kind: event.at for event in parsing.timeline_events(text)
        }
        assert_that(found, equal_to({"labeled": LABELED["created_at"], "committed": ""}))

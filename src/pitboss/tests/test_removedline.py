"""Tests for the REMOVED FROM QUEUE line (keyword: removed-from-queue, pitboss#138).

The fixtures are the case of bats-lang/quire#1032: the queue added the PR at
22:44:11 and removed it at 23:28:52, and a job of the group's run had failed.
"""

import dataclasses
import json
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import (
    config,
    finishpartial,
    parsing,
    pulls,
    queue,
    removedline,
    report,
    reviews,
    shapes,
    steps,
    tasklist,
)
from . import fakes, pressureworld, quietworld, test_work, world
from .queueworld import (
    DISABLED,
    ENABLED,
    FAILED_JOB,
    PASSED_JOB,
    QUEUE_BRANCH,
    project_page,
    removed_world,
)
from .test_commands import sweep

ADDED = {"event": "added_to_merge_queue", "created_at": "2029-12-31T22:44:11Z"}
REMOVED = {"event": "removed_from_merge_queue", "created_at": "2029-12-31T23:28:52Z"}
ADDED_AGAIN = {"event": "added_to_merge_queue", "created_at": "2029-12-31T23:40:00Z"}
DROPPED_LINE = "DROPPED FROM QUEUE owner/project#2: 2029-12-31T23:30:00Z, "
WAIT_LINE = "WAIT-FOR-HOLD owner/project#2: a runner-pressure hold or its quiet period"
LABELED = {"event": "labeled", "created_at": "2029-12-31T20:00:00Z"}
COMMITTED = {"event": "committed"}
REMOVED_LINE = "REMOVED FROM QUEUE owner/project#2: 2029-12-31T23:28:52Z, "
FAILED_TEXT = (
    "failed job of its last queue run: android / build-android: Fetch dependencies"
)
READY_LINE = "READY TO MERGE owner/project#2: arm auto-merge"
STANDARD_LINE = READY_LINE + " or merge"
CANCELLED_JOB = {"name": "android / build-android", "conclusion": "cancelled"}
BARE_FAILED_JOB = {"name": "check / test", "conclusion": "failure"}


def lines_of(here: world.World) -> Sequence[str]:
    """The sweep's lines about PR 2 of the project.

    Args:
        here: the world.

    Returns:
        The lines that name the PR, without its summary and the finishing line.
    """
    return [
        line
        for line in sweep(here).out.splitlines()
        if "owner/project#2" in line
        and not line.startswith(
            ("owner/project#2 [", tasklist.LABEL, finishpartial.PREFIX)
        )
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
        expected = (
            REMOVED_LINE + "no failed job in its last queue run: cancelled by the queue"
        )
        assert_that(lines_of(here), equal_to([expected, READY_LINE]))

    def test_a_failed_job_with_no_failed_step(self) -> None:
        """A failed job whose steps were not read says so."""
        here = removed_world([ADDED, REMOVED], [BARE_FAILED_JOB])
        expected = (
            REMOVED_LINE
            + "failed job of its last queue run: check / test: no failed step read"
        )
        assert_that(lines_of(here), equal_to([expected, READY_LINE]))

    def test_the_removal_is_found_on_a_later_page(self) -> None:
        """A timeline of more than a page is read to its end."""
        first = [LABELED] * 99 + [ADDED]
        here = removed_world(first, [FAILED_JOB])
        here.bodies[project_page("issues/2/timeline", 2)] = [REMOVED]
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
        assert_that(removedline.removed_at([]), equal_to(None))

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
        here.bodies[project_page("issues/2/timeline")] = fakes.REFUSED
        expected = "UNREADABLE owner/project#2: timeline answered HTTP 404"
        assert_that(expected in lines_of(here), equal_to(True))

    def test_an_unreadable_job_list_is_said(self) -> None:
        """A failing jobs call is an UNREADABLE line naming the call."""
        here = removed_world([ADDED, REMOVED], [FAILED_JOB])
        del here.bodies[project_page("actions/runs/12/jobs")]
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


ALONE = REMOVED_LINE + FAILED_TEXT
SAID = removedline.Said(lines=["R"], removed=True, act="A")


def reviewed(here: world.World, reviews_of_pr: Sequence[object]) -> world.World:
    """Give PR 2 these reviews and no review comment.

    Args:
        here: the world.
        reviews_of_pr: the PR's GitHub reviews.

    Returns:
        The world.
    """
    pages = [("pulls/2/reviews", list(reviews_of_pr)), ("issues/2/comments", [])]
    here.bodies.update(fakes.bodies_under(world.PROJECT, pages))
    return here


class TestStanding(unittest.TestCase):
    """The action is told only for the standing READY TO MERGE needs."""

    def test_a_review_of_an_older_head_gets_the_removal_alone(self) -> None:
        """Arming auto-merge could merge a head nobody approved."""
        old = dict(world.APPROVAL, commit_id=fakes.OLDER)
        here = removed_world([ADDED, REMOVED], [FAILED_JOB])
        compare = f"{world.PROJECT}/compare/main..."
        authored = {"sha": "1", "parents": [{"sha": "0"}]}
        fix = {"sha": "2", "parents": [{"sha": "1"}]}
        here.bodies[compare + fakes.HEAD] = {"commits": [authored, fix]}
        here.bodies[compare + fakes.OLDER] = {"commits": [authored]}
        listed = {"files": [{"filename": "a.bats"}]}
        here.bodies.update({f"{world.PROJECT}/commits/2": listed})
        assert_that(lines_of(reviewed(here, [old])), equal_to([ALONE]))

    def test_no_review_gets_the_removal_alone(self) -> None:
        """A PR nobody reviewed is not told to arm auto-merge."""
        here = removed_world([ADDED, REMOVED], [FAILED_JOB])
        assert_that(lines_of(reviewed(here, [])), equal_to([ALONE]))


held = pressureworld.held


class TestDropped(unittest.TestCase):
    """A PR armed and then dropped with no removal is named and re-armed.

    Quire#1110.
    """

    def test_c26_a_pr_whose_auto_merge_was_switched_off_is_dropped_from_the_queue(
        self,
    ) -> None:
        """Enabled, then disabled, not in the queue and not merged."""
        here = removed_world([ENABLED, DISABLED], [FAILED_JOB])
        found = lines_of(here)
        assert_that(found[0].startswith(DROPPED_LINE), equal_to(True))
        assert_that(found[1:], equal_to([READY_LINE]))

    def test_c26_a_removal_is_a_removal_even_when_auto_merge_was_switched_off_too(
        self,
    ) -> None:
        """The queue's own removal event is the cause that is named."""
        here = removed_world([ADDED, REMOVED, DISABLED], [FAILED_JOB])
        assert_that(lines_of(here)[0].startswith(REMOVED_LINE), equal_to(True))

    def test_c26_a_pr_armed_again_after_the_switch_off_is_not_dropped(self) -> None:
        """The newest arming ends the drop."""
        here = removed_world([ENABLED, DISABLED, ADDED_AGAIN], [FAILED_JOB])
        assert_that(lines_of(here), equal_to([STANDARD_LINE]))

    def test_c26_a_switched_off_auto_merge_of_an_unapproved_head_is_not_a_drop(
        self,
    ) -> None:
        """A push turns auto-merge off; a head nobody approved has nothing to re-arm."""
        here = removed_world([ENABLED, DISABLED], [FAILED_JOB])
        assert_that(lines_of(reviewed(here, [])), equal_to([]))

    def test_c26_the_hold_withholds_the_re_arm_and_says_wait(self) -> None:
        """During the hold the line is WAIT-FOR-HOLD, never the arm."""
        here = held(removed_world([ENABLED, DISABLED], [FAILED_JOB]))
        found = lines_of(here)
        assert_that(found[0].startswith(DROPPED_LINE), equal_to(True))
        assert_that(len(found), equal_to(2))
        assert_that(found[1].startswith(WAIT_LINE), equal_to(True))
        assert_that(READY_LINE in found, equal_to(False))

    def test_c26_the_hold_withholds_the_re_arm_of_a_removal_too(self) -> None:
        """A removal's act is gated like the drop's."""
        here = held(removed_world([ADDED, REMOVED], [FAILED_JOB]))
        found = lines_of(here)
        assert_that(
            [READY_LINE in found, found[-1].startswith(WAIT_LINE)],
            equal_to([False, True]),
        )

    def test_c26_the_re_arm_is_offered_again_once_the_hold_ends(self) -> None:
        """The same PR, the record clear: the arm line is there."""
        here = held(removed_world([ENABLED, DISABLED], [FAILED_JOB]))
        assert_that(lines_of(quietworld.at_rest(here))[1:], equal_to([READY_LINE]))

    def test_c26_the_hold_withholds_a_ready_pr_and_a_behind_pr_alike(self) -> None:
        """READY TO MERGE and AUTO MERGE OFF are not offered during the hold."""
        here = held(removed_world([], []))
        found = lines_of(here)
        assert_that(found, equal_to([found[0]]))
        assert_that(found[0].startswith(WAIT_LINE), equal_to(True))


class TestUnits(unittest.TestCase):
    """The pieces alone."""

    def test_no_queue_run_read(self) -> None:
        """With no run of the PR among those read, the line says so."""
        removal = removedline.Removal(at="T", runs=0, failed=[])
        found = removedline.line(facts(), removal)
        expected = f"REMOVED FROM QUEUE owner/project#2: T, {removedline.NOT_READ}"
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

    def test_the_action_follows_the_standing_lines(self) -> None:
        """The action is printed with a READY TO MERGE or AUTO MERGE OFF line."""
        other = "FAILED x"
        found = [
            removedline.settle(SAID, acts)
            for acts in (
                [READY_LINE + " or merge"],
                ["AUTO MERGE OFF x: arm it again", other],
                [other],
                [],
            )
        ]
        expected = [["R", "A"], ["R", "A", other], ["R", other], ["R"]]
        assert_that(found, equal_to(expected))

    def test_a_ruling_approved_head_gets_the_action(self) -> None:
        """The report's own check says READY TO MERGE for the Opus ruling."""
        pull = dataclasses.replace(
            facts(), standing=reviews.Standing.CHANGES_NEEDED, step=steps.merge()
        )
        settings = fakes.settings(fakes.directory())
        acts = report.action_lines(pull, settings, False, {})
        assert_that(removedline.settle(SAID, acts), equal_to(["R", "A"]))

    def test_events_of_other_kinds_are_kept_for_paging(self) -> None:
        """The parser keeps every event, so a full page of them pages on."""
        text = json.dumps([LABELED, COMMITTED])
        found: Mapping[str, str] = {
            event.kind: event.at for event in parsing.timeline_events(text)
        }
        assert_that(
            found, equal_to({"labeled": LABELED["created_at"], "committed": ""})
        )

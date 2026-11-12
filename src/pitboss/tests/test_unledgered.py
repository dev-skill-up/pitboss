"""C17: the sweep names GitHub events no ``pitboss act`` record answers (promise#73).

A merge made around a runner-pressure hold by a raw ``gh`` call has no record in the
ledger; the sweep names it with the event's id (keyword: action-matrix).
"""

import dataclasses
import datetime
import json
import unittest
from typing import Mapping

from hamcrest import assert_that, empty, equal_to

from .. import actions, actrun, logline, steps, unledgered
from . import test_flow_sweep, world
from .says import says

PULL = "owner/project#3"
MOMENT = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)


def at(minutes: int) -> datetime.datetime:
    """A time after ``MOMENT``.

    Args:
        minutes: how long after.

    Returns:
        The time.
    """
    return MOMENT + datetime.timedelta(minutes=minutes)


def seen(identifier: str, action: actions.Action, minutes: int) -> unledgered.Seen:
    """An event of GitHub on PR 3.

    Args:
        identifier: its id.
        action: what it was.
        minutes: when, after ``MOMENT``.

    Returns:
        The event.
    """
    return unledgered.Seen(
        identifier=identifier,
        action=action,
        repository="owner/project",
        reference=PULL,
        branch="",
        time=at(minutes),
    )


STEP = steps.Next(step=steps.Step.MERGE)


def record(action: actions.Action, minutes: int, number: int = 3) -> logline.Event:
    """The record of ``pitboss act`` on a PR of the project.

    Args:
        action: the action.
        minutes: when, after ``MOMENT``.
        number: the PR's number.

    Returns:
        The event.
    """
    target = actrun.Target(head="h", branch="b", number=number, slug="owner/project")
    return actrun.record(action, target, STEP, at(minutes))


def issue_event(
    identifier: int, name: str, number: int, hour: int
) -> Mapping[str, object]:
    """An event of ``issues/events`` on a PR.

    Args:
        identifier: its id.
        name: GitHub's name of the event.
        number: the PR's number.
        hour: when, in November 1.

    Returns:
        The event as the API gives it.
    """
    return {
        "id": identifier,
        "event": name,
        "created_at": f"2026-11-01T{hour:02}:00:00Z",
        "issue": {"number": number, "pull_request": {}},
    }


class TestFindings(unittest.TestCase):
    """The comparison of the events with the records."""

    def test_c17_promise_73_a_merge_around_the_hold_is_named_with_its_id(self) -> None:
        """A merge with no record of act is named; the one act made is not."""
        around = dataclasses.replace(
            seen("9001", actions.Action.MERGE, 5), reference="owner/promise#73"
        )
        made = seen("9002", actions.Action.MERGE, 40)
        found = unledgered.findings([made, around], [record(actions.Action.MERGE, 39)])
        said = "UNLEDGERED event 9001: merge of owner/promise#73 at 2026-11-01T12:05"
        assert_that([each[: len(said)] for each in found], equal_to([said]))

    def test_c17_a_record_answers_one_event_just_before_it(self) -> None:
        """One record names one of two closes; none after it or an hour before."""
        two = [seen("1", actions.Action.CLOSE, 3), seen("2", actions.Action.CLOSE, 4)]
        counts = {
            minutes: len(
                unledgered.findings(two, [record(actions.Action.CLOSE, minutes)])
            )
            for minutes in (2, 30, -60)
        }
        assert_that(counts, equal_to({2: 1, 30: 2, -60: 2}))

    def test_c17_a_record_of_another_action_or_pr_is_no_answer(self) -> None:
        """The action and the PR must be the same."""
        event = seen("1", actions.Action.MERGE, 3)
        records = {
            "action": record(actions.Action.CLOSE, 2),
            "pull": record(actions.Action.MERGE, 2, number=4),
            "same": record(actions.Action.MERGE, 2),
        }
        found = {
            name: len(unledgered.findings([event], [each]))
            for name, each in records.items()
        }
        assert_that(found, equal_to({"action": 1, "pull": 1, "same": 0}))

    def test_c17_a_push_is_answered_by_the_repository_and_branch(self) -> None:
        """A push names its branch, not a PR."""
        push = dataclasses.replace(
            seen("2", actions.Action.PUSH, 3), reference="", branch="b"
        )
        others = {
            "branch": dataclasses.replace(push, branch="c"),
            "repository": dataclasses.replace(push, repository="owner/lib"),
            "same": push,
        }
        answer = [record(actions.Action.PUSH, 2)]
        found = {n: len(unledgered.findings([e], answer)) for n, e in others.items()}
        assert_that(found, equal_to({"branch": 1, "repository": 1, "same": 0}))


class TestReading(unittest.TestCase):
    """GitHub's answers read as events."""

    def test_c17_issue_events_are_read_as_actions(self) -> None:
        """Closed, labeled and ready_for_review of PRs are read; assigned is not."""
        names = ("closed", "labeled", "ready_for_review", "assigned")
        items = [issue_event(n, name, n, 13) for n, name in enumerate(names, 3)]
        found = unledgered.from_issue_events("o/r", json.dumps(items))
        said = [(actions.word(e.action), e.reference) for e in found]
        wanted = [("close", "o/r#3"), ("label", "o/r#4"), ("undraft", "o/r#5")]
        assert_that(said, equal_to(wanted))

    def test_c17_a_merge_is_not_also_a_close(self) -> None:
        """GitHub gives a merged and a closed event for one merge: one act."""
        items = [issue_event(1, "merged", 3, 12), issue_event(2, "closed", 3, 12)]
        found = unledgered.from_issue_events("o/r", json.dumps(items))
        assert_that([actions.word(e.action) for e in found], equal_to(["merge"]))

    def test_c17_an_event_of_an_issue_is_not_a_pr_event(self) -> None:
        """Only an issue event of a PR (it has a pull_request) is read."""
        plain = {**issue_event(6, "closed", 7, 13), "issue": {"number": 7}}
        found = unledgered.from_issue_events("o/r", json.dumps([plain]))
        assert_that(found, empty())

    def test_c17_pushes_are_read_and_main_is_left_alone(self) -> None:
        """A push to a branch; a push to main is not a PR's, a watch is no push."""
        when = "2026-11-01T12:00:00Z"
        kinds = (("PushEvent", "work"), ("PushEvent", "main"), ("WatchEvent", "x"))
        items = [
            {
                "id": n,
                "type": kind,
                "created_at": when,
                "payload": {"ref": f"refs/heads/{ref}"},
            }
            for n, (kind, ref) in enumerate(kinds, 10)
        ]
        found = unledgered.from_push_events("o/r", json.dumps(items))
        assert_that(
            [(e.identifier, e.branch) for e in found], equal_to([("10", "work")])
        )

    def test_c17_dispatched_runs_are_read(self) -> None:
        """A dispatched run is a dispatch on its branch."""
        run = {"id": 20, "created_at": "2026-11-01T12:00:00Z", "head_branch": "work"}
        found = unledgered.from_runs("o/r", json.dumps({"workflow_runs": [run]}))
        said = [(e.identifier, e.action, e.branch, e.repository) for e in found]
        wanted = [("20", actions.Action.DISPATCH, "work", "o/r")]
        assert_that(said, equal_to(wanted))


def sweep_out(here: world.World) -> str:
    """What the sweep of a world printed.

    Args:
        here: the world.

    Returns:
        Its standard output.
    """
    return world.invoke(
        here, "sweep", "--config", here.config, "--now", world.FUTURE
    ).out


def merged_world() -> world.World:
    """A world whose GitHub has a merge of PR 3 that no record answers.

    Returns:
        The world.
    """
    here = test_flow_sweep.world_with([])
    merged = {**issue_event(777, "merged", 3, 23), "created_at": "2029-12-31T23:59:00Z"}
    runs = f"{world.PROJECT}/actions/runs?event=workflow_dispatch"
    empty_bodies = {f"{world.PROJECT}/events": [], runs: {"workflow_runs": []}}
    here.bodies.update({f"{world.PROJECT}/issues/events": [merged], **empty_bodies})
    return here


class TestSweep(unittest.TestCase):
    """The sweep, end to end."""

    def test_c17_the_sweep_names_an_unledgered_merge_and_a_repository_it_cannot_read(
        self,
    ) -> None:
        """Through the whole sweep: the event of the fake GitHub has no record."""
        here = merged_world()
        says(
            sweep_out(here),
            "UNLEDGERED event 777: merge of owner/project#3",
            "UNLEDGERED owner/lib: its events",
        )

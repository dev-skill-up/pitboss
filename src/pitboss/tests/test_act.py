"""C16 and C17: ``pitboss act`` asks the matrix, and the sweep names what it never saw.

promise#73: a PR was merged around a runner-pressure hold by a raw ``gh`` call. Every
state-changing action goes through ``pitboss act``, which refuses what the PR's step
does not allow and records what it does; the sweep names each GitHub event of these
kinds with no record (keyword: action-matrix).
"""

import datetime
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, empty, equal_to, has_length, is_

from .. import act_commands, actions, actrun, duplicatepr, logline, steps, unledgered
from . import test_flow_sweep, test_slots_rules, world

PULL = "owner/project#3"
MOMENT = datetime.datetime(2026, 11, 1, 12, 0, tzinfo=datetime.timezone.utc)


def run(here: world.World, *words: str, live: bool = False) -> world.Result:
    """Run ``act`` on PR 3 of a world.

    Args:
        here: the world.
        *words: the words after the PR.
        live: whether to change anything (``--no-dry-run``).

    Returns:
        What it did.
    """
    extra = ("--no-dry-run",) if live else ()
    return world.invoke(
        here, "act", PULL, *words, "--config", here.config, "--now", world.FUTURE, *extra
    )


def events_of(here: world.World) -> str:
    """The text of the ledger's events file.

    Args:
        here: the world.

    Returns:
        Every event, one JSON line each.
    """
    return "".join(each.read_text() for each in here.workspace.rglob("*.events"))


def conflicted() -> world.World:
    """A world whose PR 3 has a conflict: its step is the worker's.

    Returns:
        The world.
    """
    return test_flow_sweep.world_with([], mergeable_state="dirty")


class TestAct(unittest.TestCase):
    """The command."""

    def test_c17_a_refused_action_changes_and_records_nothing(self) -> None:
        """A merge at a review step is refused, naming the step that allows it."""
        here = test_flow_sweep.world_with([])
        done = run(here, "merge", live=True)
        assert_that(done.code, equal_to(2))
        assert_that(done.err, contains_string("merge is refused: the PR is at Step.REGULAR_REVIEW"))
        assert_that(done.err, contains_string("allowed at Step.MERGE"))
        assert_that([c for c in here.calls if "PUT" in c], empty())
        assert_that(events_of(here), equal_to(""))

    def test_c17_a_dry_run_records_and_changes_nothing(self) -> None:
        """The default is a dry run."""
        here = conflicted()
        done = run(here, "push", "origin", "main:refs/heads/branch-3")
        assert_that((done.code, done.out), equal_to((0, f"act: push {PULL} at WORKER\n")))
        assert_that([c for c in here.calls if c[0] == "git"], empty())
        assert_that(events_of(here), equal_to(""))

    def test_c17_an_allowed_action_is_recorded_then_made(self) -> None:
        """A push at the worker's step runs git push and writes the ledger record."""
        here = conflicted()
        done = run(here, "push", "origin", "main:refs/heads/branch-3", live=True)
        assert_that(done.code, equal_to(0))
        assert_that(
            [c for c in here.calls if c[0] == "git"],
            equal_to([["git", "push", "origin", "main:refs/heads/branch-3"]]),
        )
        written = json.loads(events_of(here))
        assert_that(written["kind"], equal_to("act"))
        assert_that(written["what"], equal_to(f"push {PULL} branch-3 at WORKER"))

    def test_c17_an_unknown_action_word_is_refused(self) -> None:
        """The second word is one of the six actions."""
        done = run(conflicted(), "frobnicate")
        assert_that((done.code, done.err), equal_to((2, done.err)))
        assert_that(done.err, contains_string("act takes the action as its second word"))
        assert_that(run(conflicted()).code, equal_to(2))

    def test_c17_a_missing_argument_is_refused(self) -> None:
        """A label needs its name; a push needs git's arguments."""
        assert_that(run(conflicted(), "label").err, contains_string("label takes the label's name"))
        assert_that(run(conflicted(), "push").err, contains_string("push takes the arguments"))

    def test_c17_a_pull_that_is_not_open_is_refused(self) -> None:
        """No PR, no action."""
        done = world.invoke(
            conflicted(), "act", "owner/project#99", "merge", "--config",
            conflicted().config, "--now", world.FUTURE,
        )
        assert_that(done.code, equal_to(2))

    def test_c17_each_action_has_its_command(self) -> None:
        """The command of every action, by what GitHub's API and gh take."""
        said = {
            each: actrun.argv(each, "o/r", 3, "b", ["w"]) for each in actions.Action
        }
        assert_that(said[actions.Action.PUSH], equal_to(["git", "push", "w"]))
        assert_that(said[actions.Action.MERGE][-1], equal_to("repos/o/r/pulls/3/merge"))
        assert_that(said[actions.Action.UNDRAFT][:3], equal_to(["gh", "pr", "ready"]))
        assert_that(said[actions.Action.DISPATCH][-2:], equal_to(["--ref", "b"]))
        assert_that(said[actions.Action.DISPATCH][3], equal_to("w"))
        assert_that(said[actions.Action.CLOSE][-1], equal_to("repos/o/r/pulls/3"))
        assert_that(said[actions.Action.LABEL][-2:], equal_to(["labels[]=w", "repos/o/r/issues/3/labels"]))

    def test_c17_a_second_pr_on_a_ticket_has_the_duplicate_standing(self) -> None:
        """The newer of two PRs on one ticket may be closed at any step."""
        first = test_slots_rules.facts(3, test_slots_rules.NONE, body="Fixes #9", created_at="2026-11-01T00:00:00Z")
        second = test_slots_rules.facts(4, test_slots_rules.NONE, body="Fixes #9", created_at="2026-11-02T00:00:00Z")
        every = [second, first]
        assert_that(duplicatepr.newer(every), equal_to({"owner/project#4"}))
        assert_that(act_commands.standing_of(second, every), equal_to(actions.Standing.DUPLICATE))
        assert_that(act_commands.standing_of(first, every), equal_to(actions.Standing.PLAIN))


def seen(identifier: str, action: actions.Action, minutes: int, reference: str = "", branch: str = "") -> unledgered.Seen:
    """An event of GitHub.

    Args:
        identifier: its id.
        action: what it was.
        minutes: when, after ``MOMENT``.
        reference: the PR.
        branch: the branch.

    Returns:
        The event.
    """
    return unledgered.Seen(
        identifier=identifier, action=action, reference=reference, branch=branch,
        time=MOMENT + datetime.timedelta(minutes=minutes),
    )


def record(action: actions.Action, minutes: int, reference: str = PULL, branch: str = "b") -> logline.Event:
    """The record of ``pitboss act``.

    Args:
        action: the action.
        minutes: when, after ``MOMENT``.
        reference: the PR.
        branch: its branch.

    Returns:
        The event.
    """
    return actrun.record(
        action, reference, branch, steps.Next(step=steps.Step.MERGE), "h",
        MOMENT + datetime.timedelta(minutes=minutes),
    )


class TestUnledgered(unittest.TestCase):
    """The sweep's comparison of GitHub's events with the ledger."""

    def test_c17_promise_73_a_merge_around_the_hold_is_named_with_its_id(self) -> None:
        """A merge with no record of act is named; the one act made is not."""
        around = seen("9001", actions.Action.MERGE, 5, reference="owner/promise#73")
        made = seen("9002", actions.Action.MERGE, 40, reference=PULL)
        records = [record(actions.Action.MERGE, 39)]
        found = unledgered.findings([made, around], records)
        assert_that(found, has_length(1))
        assert_that(found[0], contains_string("UNLEDGERED event 9001: merge of owner/promise#73"))

    def test_c17_a_record_answers_one_event_and_only_just_before_it(self) -> None:
        """Two merges with one record: one is named; a record after the event is no answer."""
        two = [seen("1", actions.Action.CLOSE, 3, reference=PULL), seen("2", actions.Action.CLOSE, 4, reference=PULL)]
        one_record = [record(actions.Action.CLOSE, 2)]
        assert_that(unledgered.findings(two, one_record), has_length(1))
        late = [record(actions.Action.CLOSE, 30)]
        assert_that(unledgered.findings(two[:1], late), has_length(1))
        old = [record(actions.Action.CLOSE, -60)]
        assert_that(unledgered.findings(two[:1], old), has_length(1))

    def test_c17_a_record_of_another_action_or_pr_is_no_answer(self) -> None:
        """The action and the PR (or the branch) must be the same."""
        event = seen("1", actions.Action.MERGE, 3, reference=PULL)
        assert_that(unledgered.findings([event], [record(actions.Action.CLOSE, 2)]), has_length(1))
        assert_that(unledgered.findings([event], [record(actions.Action.MERGE, 2, reference="owner/project#4")]), has_length(1))
        push = seen("2", actions.Action.PUSH, 3, branch="b")
        assert_that(unledgered.findings([push], [record(actions.Action.PUSH, 2, branch="b")]), empty())
        assert_that(unledgered.findings([push], [record(actions.Action.PUSH, 2, branch="c")]), has_length(1))

    def test_c17_issue_events_are_read_and_a_merge_is_not_also_a_close(self) -> None:
        """Merged, closed, labeled and ready_for_review of PRs; nothing of an issue."""
        text = json.dumps([
            {"id": 1, "event": "merged", "created_at": "2026-11-01T12:00:00Z", "issue": {"number": 3, "pull_request": {}}},
            {"id": 2, "event": "closed", "created_at": "2026-11-01T12:00:00Z", "issue": {"number": 3, "pull_request": {}}},
            {"id": 3, "event": "closed", "created_at": "2026-11-01T13:00:00Z", "issue": {"number": 4, "pull_request": {}}},
            {"id": 4, "event": "labeled", "created_at": "2026-11-01T13:00:00Z", "issue": {"number": 5, "pull_request": {}}},
            {"id": 5, "event": "ready_for_review", "created_at": "2026-11-01T13:00:00Z", "issue": {"number": 6, "pull_request": {}}},
            {"id": 6, "event": "closed", "created_at": "2026-11-01T13:00:00Z", "issue": {"number": 7}},
            {"id": 7, "event": "assigned", "created_at": "2026-11-01T13:00:00Z", "issue": {"number": 8, "pull_request": {}}},
        ])
        found = unledgered.from_issue_events("o/r", text)
        assert_that(
            [(each.identifier, each.action.value, each.reference) for each in found],
            equal_to([("1", "merge", "o/r#3"), ("3", "close", "o/r#4"), ("4", "label", "o/r#5"), ("5", "undraft", "o/r#6")]),
        )

    def test_c17_push_and_dispatch_events_are_read_and_main_is_left_alone(self) -> None:
        """A push to a branch and a dispatched run; a push to main is not a PR's."""
        pushes = json.dumps([
            {"id": 10, "type": "PushEvent", "created_at": "2026-11-01T12:00:00Z", "payload": {"ref": "refs/heads/work"}},
            {"id": 11, "type": "PushEvent", "created_at": "2026-11-01T12:00:00Z", "payload": {"ref": "refs/heads/main"}},
            {"id": 12, "type": "WatchEvent", "created_at": "2026-11-01T12:00:00Z", "payload": {}},
        ])
        found = unledgered.from_push_events(pushes)
        assert_that([(e.identifier, e.branch) for e in found], equal_to([("10", "work")]))
        runs = json.dumps({"workflow_runs": [{"id": 20, "created_at": "2026-11-01T12:00:00Z", "head_branch": "work"}]})
        ran = unledgered.from_runs(runs)
        assert_that([(e.identifier, e.action, e.branch) for e in ran], equal_to([("20", actions.Action.DISPATCH, "work")]))

    def test_c17_the_sweep_names_an_unledgered_merge_and_a_repository_it_cannot_read(self) -> None:
        """Through the whole sweep: the event of the fake GitHub has no record."""
        here = test_flow_sweep.world_with([])
        merged = [{"id": 777, "event": "merged", "created_at": "2029-12-31T23:59:00Z", "issue": {"number": 3, "pull_request": {}}}]
        here.bodies[f"{world.PROJECT}/issues/events"] = merged
        here.bodies[f"{world.PROJECT}/events"] = []
        here.bodies[f"{world.PROJECT}/actions/runs?event=workflow_dispatch"] = {"workflow_runs": []}
        done = world.invoke(here, "sweep", "--config", here.config, "--now", world.FUTURE)
        assert_that(done.out, contains_string("UNLEDGERED event 777: merge of owner/project#3"))
        assert_that(done.out, contains_string("UNLEDGERED owner/lib: its events could not be read"))

"""Plan 6.1: each fact of a PR is parsed once, from GitHub's JSON, into one field."""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from pitboss import pullobject, pullrecords, pullstate, shapes

SCHEMA = {
    "number": "required, integer",
    "title": "required, string",
    "milestone": "object or null",
}
PULL: Mapping[str, object] = {
    "number": 7,
    "title": "Fix it",
    "state": "open",
    "mergeable": True,
    "mergeable_state": "clean",
    "auto_merge": None,
    "base": {"ref": "main", "repo": {"full_name": "o/r"}},
    "head": {"sha": "abc", "repo": {"full_name": "o/r"}},
    "labels": [{"name": "dependencies"}],
    "user": {"login": "bot"},
    "body": "Fixes #3",
}
REVIEWED = {"event": "reviewed", "state": "approved", "user": {"login": "r"}}
LABELED = {"event": "labeled", "actor": {"login": "a"}, "label": {"name": "x"}}


def _pull(**changed: object) -> pullrecords.PullObject:
    return pullobject.pull_object({**PULL, **changed}, SCHEMA)


def _state(**given: object) -> pullrecords.GateState:
    inputs = {name: given.get(name, []) for name in pullstate.INPUTS}
    return pullstate.parse(PULL, inputs, SCHEMA)


class TestPullObject(unittest.TestCase):
    """Plan 6.1: the PR object's fields."""

    def test_6_1_which_pr_and_whose(self) -> None:
        """Plan 6.1: the number, the base, the head and the author."""
        where = _pull().where
        got = (where.number, where.base_ref, where.head_sha, where.author)
        assert_that(got, equal_to((7, "main", "abc", "bot")))

    def test_6_1_labels_are_their_names(self) -> None:
        """Plan 6.1: the labels."""
        assert_that(list(_pull().merging.labels), equal_to(["dependencies"]))

    def test_6_1_mergeable_and_its_state(self) -> None:
        """Plan 6.1: the mergeable state; null mergeable is None."""
        computing = _pull(mergeable=None).merging.mergeable
        got = (_pull().merging.mergeable_state, computing)
        assert_that(got, equal_to(("clean", None)))

    def test_6_1_auto_merge_is_armed_or_not(self) -> None:
        """Plan 6.1: auto-merge, armed when GitHub gives an object."""
        armed = _pull(auto_merge={"merge_method": "merge"}).merging.auto_merge
        assert_that((_pull().merging.auto_merge, armed), equal_to((False, True)))

    def test_6_1_the_body_is_text(self) -> None:
        """Plan 6.1: the body; a null body is empty."""
        got = (_pull().body, _pull(body=None).body)
        assert_that(got, equal_to(("Fixes #3", "")))

    def test_6_1_a_mistyped_field_is_a_break_read_as_empty(self) -> None:
        """Plan 6.1: a value of another type than documented."""
        pull = _pull(number=True)
        want = [pullrecords.Mistyped(name="number", said="True")]
        assert_that((list(pull.breaks), pull.where.number), equal_to((want, 0)))

    def test_6_1_a_required_field_absent_is_a_break(self) -> None:
        """Plan 6.1: an unread required field."""
        raw = {name: value for name, value in PULL.items() if name != "title"}
        breaks = pullobject.pull_object(raw, SCHEMA).breaks
        want = [pullrecords.Mistyped(name="title", said="absent")]
        assert_that(list(breaks), equal_to(want))

    def test_6_1_closed_merged_and_locked(self) -> None:
        """Plan 6.1: the fields of a closed or locked PR."""
        closure = _pull(merged_by={"login": "x"}, locked=True, merged=True).closure
        got = (closure.merged_by, closure.locked, closure.merged)
        assert_that(got, equal_to(("x", True, True)))

    def test_6_1_requested_reviewers_are_counted(self) -> None:
        """Plan 6.1: requested reviewers and teams."""
        merging = _pull(requested_reviewers=[{}], requested_teams=[{}, {}]).merging
        assert_that((merging.reviewers, merging.teams), equal_to((1, 2)))


class TestInputs(unittest.TestCase):
    """Plan 6.1: the inputs read with the PR."""

    def test_6_1_checks_are_runs(self) -> None:
        """Plan 6.1: the head's check runs; a run with no conclusion says None."""
        reads = _state(check_runs=[{"name": "t", "status": "queued", "id": 4}]).reads
        want = shapes.CheckRun(
            id=4,
            name="t",
            finished=False,
            failed=False,
            head_sha="",
            started_at="",
            completed_at="",
            run=0,
            succeeded=False,
            said=("queued", "None"),
        )
        assert_that(reads.runs, equal_to([want]))

    def test_6_1_statuses_are_typed(self) -> None:
        """Plan 6.1: the head's statuses."""
        given = [{"context": "text-lint", "state": "success"}]
        want = pullrecords.Status(context="text-lint", state="success")
        assert_that(_state(statuses=given).reads.statuses, equal_to([want]))

    def test_6_1_files_give_the_diff_size(self) -> None:
        """Plan 6.1: the files; a count of another type is 0."""
        given = [{"filename": "a.py", "additions": 3, "deletions": "x"}]
        want = pullrecords.File(name="a.py", additions=3, deletions=0)
        assert_that(_state(files=given).reads.files, equal_to([want]))

    def test_6_1_a_list_github_answered_with_an_error_is_unread(self) -> None:
        """Plan 6.1: GitHub's error is the read's reason."""
        files = _state(files={"_error": "HTTP 502"}).reads.files
        assert_that(files, equal_to(pullrecords.Unread(why="HTTP 502")))

    def test_6_1_a_read_that_is_no_list_is_empty(self) -> None:
        """Plan 6.1: a value that is no list holds no item, as the gate read it."""
        assert_that(_state(statuses="odd").reads.statuses, equal_to([]))

    def test_6_1_a_member_of_another_type_is_mistyped(self) -> None:
        """Plan 6.1: a conclusion that is a list is not of GitHub's schema."""
        runs = _state(check_runs=[{"name": "t", "conclusion": [5]}]).reads.runs
        assert_that(runs, equal_to(pullrecords.Mistyped(name="conclusion", said="[5]")))

    def test_6_1_events_are_typed(self) -> None:
        """Plan 6.1: the timeline: a review's author, a label event's label."""
        timeline = _state(timeline=[REVIEWED, LABELED]).reads.timeline
        events = (
            []
            if isinstance(timeline, (pullrecords.Unread, pullrecords.Mistyped))
            else timeline
        )
        got = [(e.kind, e.state, e.login, e.label) for e in events]
        want = [("reviewed", "approved", "r", ""), ("labeled", "", "a", "x")]
        assert_that(got, equal_to(want))

    def test_6_1_tickets_are_typed_or_unread(self) -> None:
        """Plan 6.1: the tickets the body closes."""
        given = {"o/r#3": {"state": "open", "body": "b"}, "o/r#4": {"_error": "404"}}
        want = pullrecords.Ticket(
            state="open", reason="None", locked=False, is_pull=False, body="b"
        )
        unread = pullrecords.Unread(why="404")
        got = _state(tickets=given).tickets
        assert_that(got, equal_to({"o/r#3": want, "o/r#4": unread}))

    def test_6_1_holds_have_a_scope(self) -> None:
        """Plan 6.1: the holds; no scope holds all."""
        holds = _state(holds=[{"title": "h", "body": "scope=merges"}, {"number": 9}])
        got = [(each.title, each.scope) for each in holds.holds]
        assert_that(got, equal_to([("h", "merges"), ("9", "all")]))

    def test_6_1_the_repository_facts(self) -> None:
        """Plan 6.1: the rules, the identity, the authors and the limits."""
        state = _state(repo="o/r", required_checks=["c"], merge_queue=True, max_lines=4)
        repository = state.repository
        got = (repository.repo, repository.required_checks, repository.merge_queue)
        assert_that((*got, repository.max_lines), equal_to(("o/r", {"c"}, True, 4)))

    def test_6_1_the_blockers_and_the_authors(self) -> None:
        """Plan 6.1: the blockers' states; the authors as a set."""
        state = _state(blockers={"o/r#2": "open"}, authors={"bot"})
        got = (state.blockers, state.repository.authors)
        assert_that(got, equal_to(({"o/r#2": "open"}, {"bot"})))

    def test_6_1_an_input_not_given_is_named(self) -> None:
        """Plan 6.1: an input absent is explicit, never a default."""
        state = pullstate.parse(PULL, {}, SCHEMA)
        assert_that(list(state.absent), equal_to(list(pullstate.INPUTS)))

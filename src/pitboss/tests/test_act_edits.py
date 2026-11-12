"""The act verbs that edit: the body, labels, runs, closes, comments and pushes.

(keyword: act-verbs, pitboss#444): each runs the verdict and the gates.
"""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import actcore
from . import fakehub
from .actplay import GIVEN, file_issue, kinds, refusal, verb_refusal
from .knownkit import BODY, NUMBER, REPO, act, change, made
from .knowngit import git, repo_pair
from .fakes import write

SCRATCH = "bats-lang/relock-scratch"
OPEN_ISSUE = {"number": 5, "labels": "", "state": "open", "title": "t", "body": ""}
SHUTDOWN = "The runner has received a shutdown signal"
PULL = {"head": "b", "title": "t", "body": BODY}


def _review_id(hub: fakehub.Made) -> None:
    # gives the world's review comment the id 4242
    events = hub.hub.events[(REPO, NUMBER)]
    review = [
        each
        for each in events
        if isinstance(each, dict) and "Verdict:" in str(each.get("body"))
    ][0]
    review["id"] = 4242


class TestEdits(unittest.TestCase):
    """The body, labels, runs, closes and comments."""

    def test_c17_a_body_edit_needs_a_new_review(self) -> None:
        """After pr-edit the merge waits; a body with no Fixes line is refused."""
        hub = made(GIVEN)
        act(GIVEN, hub, "pr-edit", body=BODY + "\nmore")
        assert_that(refusal(hub, "merge"), contains_string("body changed"))
        assert_that(refusal(hub, "pr-edit", body="hello"), contains_string("Fixes"))

    def test_c17_runs_and_labels(self) -> None:
        """A rerun needs a runner cause; a label in no row is refused."""
        hub = made(GIVEN)
        coded = refusal(hub, "rerun", run="1", cause="code")
        assert_that(coded, contains_string("runner"))
        act(GIVEN, hub, "rerun", run="1", cause="runner", evidence=SHUTDOWN)
        assert_that(refusal(hub, "label", name="lgtm"), contains_string("lgtm"))
        assert_that(kinds(hub), equal_to(["rerun"]))

    def test_c17_workflows_cancels_and_closes(self) -> None:
        """Each refusal of its row, and the write when allowed."""
        hub = made(GIVEN)
        deploy = refusal(hub, "dispatch-workflow", workflow="deploy.yml", ref="main")
        assert_that(deploy, contains_string("deploy.yml"))
        act(GIVEN, hub, "dispatch-workflow", workflow="relock.yml", ref="main")
        act(GIVEN, hub, "cancel", run="7", superseded_by="8")
        reasonless = refusal(hub, "close", number="5", reason="because")
        assert_that(reasonless, contains_string("state_reason"))
        file_issue(hub, 5, dict(OPEN_ISSUE))
        act(GIVEN, hub, "close", number="5", reason="completed")
        assert_that(kinds(hub), equal_to(["dispatch", "cancel", "close-issue"]))

    def test_c17_comments_are_edited_only_when_they_are_pitboss_own_evidence(
        self,
    ) -> None:
        """A review comment is never edited or deleted, nor evidence made a verdict."""
        hub = made(GIVEN)
        identifier = act(GIVEN, hub, "comment", body="evidence: the run log")
        act(GIVEN, hub, "comment-edit", id=identifier, body="evidence: newer")
        _review_id(hub)
        said = [
            refusal(hub, "comment-edit", id="4242", body="x"),
            refusal(hub, "comment-delete", id="4242"),
            refusal(hub, "comment-edit", id=identifier, body="Verdict: approved"),
        ]
        assert_that(["key" in each for each in said], equal_to([True, True, True]))
        gone = refusal(hub, "comment-delete", id="1")
        assert_that(gone, contains_string("not a comment"))
        act(GIVEN, hub, "comment-delete", id=identifier)
        assert_that(kinds(hub), equal_to(["comment", "comment-edit", "comment-delete"]))

    def test_c17_scratch_clean_only_in_a_scratch_repository(self) -> None:
        """A branch and a PR of the scratch repository are cleaned; not elsewhere."""
        hub = made(GIVEN)
        here = refusal(hub, "scratch-clean", branch="b")
        assert_that(here, contains_string("scratch"))
        branch = {"branch": "gate-test"}
        act(GIVEN, hub, "scratch-clean", repo=SCRATCH, number="31", **branch)
        act(GIVEN, hub, "scratch-clean", repo=SCRATCH, number="0")
        assert_that(kinds(hub), equal_to(["branch-delete", "pr-close"]))

    def test_c17_pr_create_needs_a_ticket_in_the_form(self) -> None:
        """The ticket's body is read and the body's rows are checked."""
        hub = made(GIVEN)
        ticket = "## Done when\n\n- x demonstrated by y\n"
        made_pr = act(
            GIVEN, hub, "pr-create", repo=REPO, number="0", ticket=ticket, **PULL
        )
        assert_that(made_pr, has_length(3))
        itemless = refusal(hub, "pr-create", ticket="no items", **PULL)
        assert_that(itemless, contains_string("Done when"))


class TestPushAndQueue(unittest.TestCase):
    """A push leaves auto-merge and the queue; main and a dirty tree are refused."""

    def test_c17_a_push_to_a_queued_armed_pr_disarms_and_dequeues(self) -> None:
        """Both writes come before the push, each with its record."""
        worktree = repo_pair()
        armed = change(
            pull={"auto_merge": {"merge_method": "merge"}, "node_id": "PR_1"},
            events=[{"event": "added_to_merge_queue"}],
        )
        hub = made(GIVEN, armed)
        world = dataclasses.replace(hub.act, prepush=lambda: (0, "ok\n"))
        options = {"worktree": str(worktree), "branch": "worker/7"}
        GIVEN.verbs["push"](world, actcore.Target(repo=REPO, number=NUMBER), options)
        assert_that(
            kinds(hub)[:4], equal_to(["disarm", "comment", "dequeue", "comment"])
        )
        act(GIVEN, hub, "disarm")
        assert_that(kinds(hub)[-1], equal_to("disarm"))

    def test_c17_the_default_branch_and_a_dirty_tree(self) -> None:
        """A push to main is refused; clean keeps a tree with changes."""
        worktree = repo_pair()
        git(worktree, "checkout", "-q", "main")
        hub = made(GIVEN)
        world = dataclasses.replace(hub.act, prepush=lambda: (0, "ok\n"))
        options = {"worktree": str(worktree), "branch": "main"}
        target = actcore.Target(repo=REPO)
        pushed = verb_refusal("push", world, target, options)
        assert_that(pushed, contains_string("default branch"))
        write(worktree / "loose", "x")
        cleaned = verb_refusal("clean", world, target, options)
        assert_that(cleaned, contains_string("not committed"))

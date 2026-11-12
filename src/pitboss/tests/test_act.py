"""The act verbs (keyword: act-verbs, pitboss#444): each runs the verdict and the gates."""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, empty, equal_to, has_length

from .. import actcore, actwrite, totalverdict
from . import fakehub
from .knownkit import (
    BASE,
    BODY,
    HEAD,
    NUMBER,
    REPO,
    act,
    change,
    git,
    kit,
    made,
    refused,
    repo_pair,
    verdict,
)
from .totalworld import World

GIVEN = kit()
RED = {
    "check_runs": [{"name": "check", "status": "completed", "conclusion": "failure"}]
}


def _red() -> World:
    runs = [dict(each, conclusion="failure") if each.get("name") == "check" else each for each in BASE.ctx["check_runs"]]  # type: ignore[attr-defined]
    return change(ctx={"check_runs": runs})


def _kinds(hub: fakehub.Made) -> list[str]:
    return [each.kind for each in hub.hub.writes]


class TestMerge(unittest.TestCase):
    """Merge, arm and the owner gate."""

    def test_c17_merge_on_the_go_world_writes_the_merge(self) -> None:
        """The GO world merges."""
        hub = made(GIVEN)
        act(GIVEN, hub, "merge")
        assert_that(_kinds(hub), equal_to(["merge"]))

    def test_c17_a_failed_check_refuses_the_merge_and_writes_nothing(self) -> None:
        """A STOP writes nothing."""
        hub = made(GIVEN, _red())
        assert_that(refused(lambda: act(GIVEN, hub, "merge")), contains_string("check"))
        assert_that(hub.hub.writes, empty())

    def test_c17_an_owner_message_with_no_disposition_refuses(self) -> None:
        """An ack none needs a quote; after it the merge goes and the note is filed."""
        hub = made(GIVEN, owner=actcore.Owner(messages=["m1"]))
        assert_that(refused(lambda: act(GIVEN, hub, "merge")), contains_string("m1"))
        assert_that(
            refused(
                lambda: act(
                    GIVEN,
                    hub,
                    "ack",
                    message="m1",
                    kind="none",
                    reason="no action needed here",
                )
            ),
            contains_string("quote"),
        )
        act(
            GIVEN,
            hub,
            "ack",
            message="m1",
            kind="none",
            quote="thanks",
            reason="an acknowledgement, nothing to change",
        )
        act(GIVEN, hub, "merge")
        notes = [
            each
            for each in hub.hub.issues_made.values()
            if each.get("labels") == actwrite.ACK_LABEL
        ]
        assert_that(
            (len(notes), "> thanks" in str(notes[0]["body"]), _kinds(hub)[-1]),
            equal_to((1, True, "merge")),
        )

    def test_c17_ack_hold_holds_every_repository(self) -> None:
        """A hold of all is an issue in each repository; it refuses arm."""
        hub = fakehub.made(
            BASE,
            GIVEN.controls,
            actcore.Owner(messages=["m2"]),
            [REPO, "bats-lang/pwa"],
        )
        act(
            GIVEN,
            hub,
            "ack",
            repo="all",
            number="0",
            message="m2",
            kind="hold",
            scope="merges",
        )
        held = sorted(
            where
            for (where, _), issue in hub.hub.issues_made.items()
            if issue.get("labels") == actcore.HOLD_LABEL
        )
        assert_that(held, equal_to(sorted([REPO, "bats-lang/pwa"])))
        assert_that(refused(lambda: act(GIVEN, hub, "arm")), contains_string("hold"))

    def test_c17_ack_kinds(self) -> None:
        """A ruling names its reference; cap sets the cap; a kind in no row is refused."""
        hub = made(GIVEN)
        assert_that(
            refused(
                lambda: act(
                    GIVEN,
                    hub,
                    "ack",
                    message="m3",
                    kind="ruling",
                    reason="the owner said so",
                )
            ),
            contains_string("URL"),
        )
        assert_that(
            refused(lambda: act(GIVEN, hub, "ack", message="m3", kind="maybe")),
            contains_string("ack is"),
        )
        act(GIVEN, hub, "ack", message="m4", kind="cap", cap="3")
        act(GIVEN, hub, "ack", message="m5", kind="ruling", reason="#12")
        assert_that(
            (hub.act.owner.cap, hub.act.owner.dispositions),
            equal_to((3, {"m4": "cap", "m5": "ruling"})),
        )

    def test_c17_arm_records_then_enables_and_the_gate_passes_it(self) -> None:
        """The arm record comes before auto-merge, and the verdict reads its own arming."""
        hub = made(GIVEN)
        act(GIVEN, hub, "arm")
        timeline = hub.hub.timeline(REPO, NUMBER)
        assert_that(timeline[-1]["body"], equal_to(f"pitboss-act: arm head={HEAD}"))  # type: ignore[index]
        pull = hub.hub.pull(REPO, NUMBER)
        world = World(pull=pull, ctx={**BASE.ctx, "timeline": timeline})
        assert_that(
            (pull["auto_merge"] is not None, verdict(GIVEN, "merge", world).word),
            equal_to((True, totalverdict.GO)),
        )


class TestReview(unittest.TestCase):
    """The review the verdict reads."""

    def test_c17_act_review_is_read_as_an_approval(self) -> None:
        """A review written by the verb approves this head, body and tickets."""
        world = change(ctx={"timeline": list(BASE.ctx["timeline"])[:1]})  # type: ignore[call-overload]
        hub = made(GIVEN, world)
        assert_that(
            refused(lambda: act(GIVEN, hub, "merge")), contains_string("review")
        )
        grades = {"plan": "approved", "execution": "approved", "verdict": "approved"}
        act(
            GIVEN,
            hub,
            "review",
            findings="Findings: the change does what the ticket says.",
            **grades,
        )
        timeline = hub.hub.timeline(REPO, NUMBER)
        assert_that(
            verdict(GIVEN, "merge", change(ctx={"timeline": timeline})).word,
            equal_to(totalverdict.GO),
        )

    def test_c17_grade_lines_are_refused(self) -> None:
        """Findings with a grade key, a grade in another form, a comment with a Verdict line."""
        hub = made(GIVEN)
        grades = {"plan": "approved", "execution": "approved", "verdict": "approved"}
        assert_that(
            refused(
                lambda: act(
                    GIVEN, hub, "review", findings="Verdict: approved", **grades
                )
            ),
            contains_string("key"),
        )
        assert_that(
            refused(
                lambda: act(
                    GIVEN, hub, "review", findings="x", **{**grades, "plan": "ok"}
                )
            ),
            contains_string("grade"),
        )
        assert_that(
            refused(lambda: act(GIVEN, hub, "comment", body="ok\nVerdict: approved")),
            contains_string("key"),
        )
        act(GIVEN, hub, "comment", body="the run log is attached")
        assert_that(_kinds(hub), equal_to(["comment"]))


class TestTickets(unittest.TestCase):
    """Tickets in the reader's form."""

    def test_c17_a_ticket_over_the_p90_needs_a_ruling(self) -> None:
        """Over the p90 with no ruling is refused; within it, or with one, is filed."""
        hub = made(GIVEN)
        words = {
            "title": "t",
            "done_when": "x demonstrated by y",
            "paths": "src/",
            "priority": "p1",
        }
        assert_that(
            refused(lambda: act(GIVEN, hub, "ticket", max_lines="3000", **words)),
            contains_string("p90"),
        )
        assert_that(
            act(GIVEN, hub, "ticket", max_lines="400", **words).isdigit(),
            equal_to(True),
        )
        assert_that(
            act(GIVEN, hub, "ticket", max_lines="3000", ruling="#5", **words).isdigit(),
            equal_to(True),
        )
        assert_that(
            refused(
                lambda: act(
                    GIVEN, hub, "ticket", max_lines="10", **{**words, "paths": ""}
                )
            ),
            contains_string("paths"),
        )


class TestOverride(unittest.TestCase):
    """Overrides lift one line, never a failed check."""

    def test_c17_a_failed_check_is_not_overridden(self) -> None:
        """A check line is refused."""
        world = _red()
        line = [
            each
            for each in verdict(GIVEN, "merge", world).lines
            if each.startswith("check ")
        ][0]
        assert_that(
            refused(
                lambda: act(
                    GIVEN,
                    made(GIVEN, world),
                    "override",
                    stop=line,
                    reason="known flake",
                )
            ),
            contains_string("not overridable"),
        )

    def test_c17_a_diff_stop_is_lifted_by_its_override(self) -> None:
        """The record lifts that one line for that head."""
        world = change(
            ctx={
                "files": [
                    {
                        "filename": "src/x.bats",
                        "status": "modified",
                        "additions": 600,
                        "deletions": 0,
                    }
                ]
            }
        )
        line = [
            each
            for each in verdict(GIVEN, "merge", world).lines
            if each.startswith("diff:")
        ][0]
        hub = made(GIVEN, world)
        assert_that(
            refused(
                lambda: act(
                    GIVEN,
                    hub,
                    "override",
                    stop="no such line",
                    reason="owner ruling quire#1200",
                )
            ),
            contains_string("not a stop"),
        )
        act(
            GIVEN,
            hub,
            "override",
            stop=line,
            reason="owner ruling quire#1200: the generated table counts",
        )
        act(GIVEN, hub, "merge")
        assert_that(_kinds(hub)[-1], equal_to("merge"))


class TestEdits(unittest.TestCase):
    """The body, labels, runs, closes and comments."""

    def test_c17_a_body_edit_needs_a_new_review(self) -> None:
        """After pr-edit the merge waits; a body with no Fixes line is refused."""
        hub = made(GIVEN)
        act(GIVEN, hub, "pr-edit", body=BODY + "\nmore")
        assert_that(
            refused(lambda: act(GIVEN, hub, "merge")), contains_string("body changed")
        )
        assert_that(
            refused(lambda: act(GIVEN, hub, "pr-edit", body="hello")),
            contains_string("Fixes"),
        )

    def test_c17_runs_labels_and_workflows(self) -> None:
        """Each refusal of its row, and the write when allowed."""
        hub = made(GIVEN)
        assert_that(
            refused(lambda: act(GIVEN, hub, "rerun", run="1", cause="code")),
            contains_string("runner"),
        )
        act(
            GIVEN,
            hub,
            "rerun",
            run="1",
            cause="runner",
            evidence="The runner has received a shutdown signal",
        )
        assert_that(
            refused(lambda: act(GIVEN, hub, "label", name="lgtm")),
            contains_string("lgtm"),
        )
        assert_that(
            refused(
                lambda: act(
                    GIVEN, hub, "dispatch-workflow", workflow="deploy.yml", ref="main"
                )
            ),
            contains_string("deploy.yml"),
        )
        act(GIVEN, hub, "dispatch-workflow", workflow="relock.yml", ref="main")
        act(GIVEN, hub, "cancel", run="7", superseded_by="8")
        assert_that(
            refused(lambda: act(GIVEN, hub, "close", number="5", reason="because")),
            contains_string("state_reason"),
        )
        hub.hub.issues_made[(REPO, 5)] = {
            "number": 5,
            "labels": "",
            "state": "open",
            "title": "t",
            "body": "",
        }
        act(GIVEN, hub, "close", number="5", reason="completed")
        assert_that(
            _kinds(hub), equal_to(["rerun", "dispatch", "cancel", "close-issue"])
        )

    def test_c17_update_branch_under_a_hold_is_refused(self) -> None:
        """A hold of all scopes refuses update-branch."""
        hub = made(GIVEN)
        act(GIVEN, hub, "update-branch")
        hub.hub.issues_made[(REPO, 900)] = {
            "number": 900,
            "labels": actcore.HOLD_LABEL,
            "state": "open",
            "title": "h",
            "body": "scope=all\nfrom=m",
        }
        assert_that(
            refused(lambda: act(GIVEN, hub, "update-branch")), contains_string("hold")
        )
        act(GIVEN, hub, "unhold", number="900")
        act(GIVEN, hub, "update-branch")
        assert_that(
            _kinds(hub), equal_to(["update-branch", "close-issue", "update-branch"])
        )

    def test_c17_comments_are_edited_only_when_they_are_pitboss_own_evidence(
        self,
    ) -> None:
        """A review comment is never edited or deleted, nor evidence turned into a verdict."""
        hub = made(GIVEN)
        identifier = act(GIVEN, hub, "comment", body="evidence: the run log")
        act(
            GIVEN,
            hub,
            "comment-edit",
            id=identifier,
            body="evidence: the newer run log",
        )
        review = [each for each in hub.hub.events[(REPO, NUMBER)] if "Verdict:" in str(each.get("body"))][0]  # type: ignore[attr-defined]
        review["id"] = 4242  # type: ignore[index]
        assert_that(
            refused(lambda: act(GIVEN, hub, "comment-edit", id="4242", body="x")),
            contains_string("key"),
        )
        assert_that(
            refused(lambda: act(GIVEN, hub, "comment-delete", id="4242")),
            contains_string("key"),
        )
        assert_that(
            refused(lambda: act(GIVEN, hub, "comment-delete", id="1")),
            contains_string("not a comment"),
        )
        assert_that(
            refused(
                lambda: act(
                    GIVEN, hub, "comment-edit", id=identifier, body="Verdict: approved"
                )
            ),
            contains_string("key"),
        )
        act(GIVEN, hub, "comment-delete", id=identifier)
        assert_that(
            _kinds(hub), equal_to(["comment", "comment-edit", "comment-delete"])
        )

    def test_c17_scratch_clean_only_in_a_scratch_repository(self) -> None:
        """A branch and a PR of the scratch repository are cleaned; elsewhere it is refused."""
        hub = made(GIVEN)
        assert_that(
            refused(lambda: act(GIVEN, hub, "scratch-clean", branch="b")),
            contains_string("scratch"),
        )
        act(
            GIVEN,
            hub,
            "scratch-clean",
            repo="bats-lang/relock-scratch",
            number="31",
            branch="gate-test",
        )
        act(GIVEN, hub, "scratch-clean", repo="bats-lang/relock-scratch", number="0")
        assert_that(_kinds(hub), equal_to(["branch-delete", "pr-close"]))

    def test_c17_pr_create_needs_a_ticket_in_the_form(self) -> None:
        """The ticket's body is read and the body's rows are checked."""
        hub = made(GIVEN)
        ticket = "## Done when\n\n- x demonstrated by y\n"
        assert_that(
            act(
                GIVEN,
                hub,
                "pr-create",
                repo=REPO,
                number="0",
                head="b",
                title="t",
                body=BODY,
                ticket=ticket,
            ),
            has_length(3),
        )
        assert_that(
            refused(
                lambda: act(
                    GIVEN,
                    hub,
                    "pr-create",
                    head="b",
                    title="t",
                    body=BODY,
                    ticket="no items",
                )
            ),
            contains_string("Done when"),
        )


class TestPushAndQueue(unittest.TestCase):
    """A push leaves auto-merge and the queue; the default branch and a dirty tree are refused."""

    def test_c17_a_push_to_a_queued_armed_pr_disarms_and_dequeues(self) -> None:
        """Both writes come before the push, each with its record."""
        worktree = repo_pair()
        armed = change(
            pull={"auto_merge": {"merge_method": "merge"}, "node_id": "PR_1"},
            events=[{"event": "added_to_merge_queue"}],
        )
        hub = made(GIVEN, armed)
        world = dataclasses.replace(hub.act, prepush=lambda: (0, "ok\n"))
        GIVEN.verbs["push"](
            world,
            actcore.Target(repo=REPO, number=NUMBER),
            {"worktree": str(worktree), "branch": "worker/7"},
        )
        assert_that(
            _kinds(hub)[:4], equal_to(["disarm", "comment", "dequeue", "comment"])
        )
        act(GIVEN, hub, "disarm")
        assert_that(_kinds(hub)[-1], equal_to("disarm"))

    def test_c17_the_default_branch_and_a_dirty_tree(self) -> None:
        """A push to main is refused; clean keeps a tree with changes."""
        worktree = repo_pair()
        git(worktree, "checkout", "-q", "main")
        hub = made(GIVEN)
        world = dataclasses.replace(hub.act, prepush=lambda: (0, "ok\n"))
        options = {"worktree": str(worktree), "branch": "main"}
        assert_that(
            refused(
                lambda: GIVEN.verbs["push"](world, actcore.Target(repo=REPO), options)
            ),
            contains_string("default branch"),
        )
        (worktree / "loose").write_text("x", encoding="utf-8")
        assert_that(
            refused(
                lambda: GIVEN.verbs["clean"](world, actcore.Target(repo=REPO), options)
            ),
            contains_string("not committed"),
        )

    def test_c17_a_hold_of_another_repository_holds_nothing_here(self) -> None:
        """A hold of every scope in another repository leaves this one's merge alone."""
        hub = fakehub.made(BASE, GIVEN.controls, None, [REPO, "bats-lang/pwa"])
        hub.hub.issues_made[("bats-lang/pwa", 902)] = {
            "number": 902,
            "labels": actcore.HOLD_LABEL,
            "state": "open",
            "title": "h",
            "body": "scope=all\nfrom=m",
        }
        act(GIVEN, hub, "merge")
        assert_that(_kinds(hub), equal_to(["merge"]))

    def test_c17_a_hold_of_another_scope_holds_nothing_here(self) -> None:
        """An undraft hold leaves merge alone; a title-only edit checks no body."""
        hub = made(GIVEN)
        hub.hub.issues_made[(REPO, 901)] = {
            "number": 901,
            "labels": actcore.HOLD_LABEL,
            "state": "open",
            "title": "h",
            "body": "scope=undrafts\nfrom=m",
        }
        act(GIVEN, hub, "merge")
        act(GIVEN, hub, "pr-edit", title="a new title")
        assert_that(_kinds(hub), equal_to(["merge", "pr-edit"]))

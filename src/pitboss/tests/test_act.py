"""The act verbs: merge, the owner gate, reviews, tickets and overrides.

(keyword: act-verbs, pitboss#444): each runs the verdict and the gates.
"""

import unittest

from hamcrest import assert_that, contains_string, empty, equal_to

from .. import actcore, totalverdict
from . import fakehub, knownkit
from .actplay import GIVEN, hold_issue, kinds, red, refusal, stop_line
from .knownkit import BASE, HEAD, NUMBER, REPO, act, change, made
from .totalworld import World

GRADES = {"plan": "approved", "execution": "approved", "verdict": "approved"}
TICKET = {
    "title": "t",
    "done_when": "x demonstrated by y",
    "paths": "src/",
    "priority": "p1",
}
BIG = {"filename": "src/x.bats", "status": "modified", "additions": 600, "deletions": 0}


def _acked(hub: fakehub.Made) -> None:
    # an ack none with a quote files the owner's note
    why = "an acknowledgement, nothing to change"
    act(GIVEN, hub, "ack", message="m1", kind="none", quote="thanks", reason=why)


class TestMerge(unittest.TestCase):
    """Merge, arm and the owner gate."""

    def test_c17_merge_on_the_go_world_writes_the_merge(self) -> None:
        """The GO world merges."""
        hub = made(GIVEN)
        act(GIVEN, hub, "merge")
        assert_that(kinds(hub), equal_to(["merge"]))

    def test_c17_a_failed_check_refuses_the_merge_and_writes_nothing(self) -> None:
        """A STOP writes nothing."""
        hub = made(GIVEN, red())
        assert_that(refusal(hub, "merge"), contains_string("check"))
        assert_that(hub.hub.writes, empty())

    def test_c17_an_owner_message_with_no_disposition_refuses(self) -> None:
        """An ack none needs a quote; after it the merge goes and the note is filed."""
        hub = made(GIVEN, owner=actcore.Owner(messages=["m1"]))
        assert_that(refusal(hub, "merge"), contains_string("m1"))
        unquoted = refusal(
            hub, "ack", message="m1", kind="none", reason="no action needed here"
        )
        assert_that(unquoted, contains_string("quote"))
        _acked(hub)
        act(GIVEN, hub, "merge")
        notes = [
            each
            for each in hub.hub.issues_made.values()
            if each.get("labels") == actcore.ACK_LABEL
        ]
        assert_that(
            (len(notes), "> thanks" in str(notes[0]["body"]), kinds(hub)[-1]),
            equal_to((1, True, "merge")),
        )

    def test_c17_ack_hold_holds_every_repository(self) -> None:
        """A hold of all is an issue in each repository; it refuses arm."""
        both = [REPO, "bats-lang/pwa"]
        hub = fakehub.made(BASE, GIVEN.controls, actcore.Owner(messages=["m2"]), both)
        options = {"repo": "all", "number": "0", "message": "m2", "scope": "merges"}
        act(GIVEN, hub, "ack", kind="hold", **options)
        held = sorted(
            where
            for (where, _), issue in hub.hub.issues_made.items()
            if issue.get("labels") == actcore.HOLD_LABEL
        )
        assert_that(held, equal_to(sorted(both)))
        assert_that(refusal(hub, "arm"), contains_string("hold"))

    def test_c17_ack_kinds(self) -> None:
        """A ruling names its reference; cap sets the cap; another kind is refused."""
        hub = made(GIVEN)
        unnamed = refusal(
            hub, "ack", message="m3", kind="ruling", reason="the owner said so"
        )
        assert_that(unnamed, contains_string("URL"))
        maybe = refusal(hub, "ack", message="m3", kind="maybe")
        assert_that(maybe, contains_string("ack is"))
        act(GIVEN, hub, "ack", message="m4", kind="cap", cap="3")
        act(GIVEN, hub, "ack", message="m5", kind="ruling", reason="#12")
        assert_that(
            (actcore.cap_of(hub.act.owner), hub.act.owner.dispositions),
            equal_to((3, {"m4": "cap", "m5": "ruling"})),
        )

    def test_c17_arm_records_then_enables_and_the_gate_passes_it(self) -> None:
        """The arm record comes before auto-merge; the verdict reads its arming."""
        hub = made(GIVEN)
        act(GIVEN, hub, "arm")
        timeline = hub.act.hub.timeline(REPO, NUMBER)
        last = timeline[-1]["body"]  # type: ignore[index]
        assert_that(last, equal_to(f"pitboss-act: arm head={HEAD}"))
        pull = hub.act.hub.pull(REPO, NUMBER)
        world = World(pull=pull, ctx={**BASE.ctx, "timeline": timeline})
        assert_that(
            (
                pull["auto_merge"] is not None,
                knownkit.verdict(GIVEN, "merge", world).word,
            ),
            equal_to((True, totalverdict.GO)),
        )


class TestReview(unittest.TestCase):
    """The review the verdict reads."""

    def test_c17_act_review_is_read_as_an_approval(self) -> None:
        """A review written by the verb approves this head, body and tickets."""
        first = list(BASE.ctx["timeline"])[:1]  # type: ignore[call-overload]
        hub = made(GIVEN, change(ctx={"timeline": first}))
        assert_that(refusal(hub, "merge"), contains_string("review"))
        findings = "Findings: the change does what the ticket says."
        act(GIVEN, hub, "review", findings=findings, **GRADES)
        timeline = hub.act.hub.timeline(REPO, NUMBER)
        assert_that(
            knownkit.verdict(GIVEN, "merge", change(ctx={"timeline": timeline})).word,
            equal_to(totalverdict.GO),
        )

    def test_c17_grade_lines_are_refused(self) -> None:
        """Findings with a grade key, a grade in another form, a Verdict comment."""
        hub = made(GIVEN)
        keyed = refusal(hub, "review", findings="Verdict: approved", **GRADES)
        assert_that(keyed, contains_string("key"))
        loose = refusal(hub, "review", findings="x", **{**GRADES, "plan": "ok"})
        assert_that(loose, contains_string("grade"))
        comment = refusal(hub, "comment", body="ok\nVerdict: approved")
        assert_that(comment, contains_string("key"))
        act(GIVEN, hub, "comment", body="the run log is attached")
        assert_that(kinds(hub), equal_to(["comment"]))


class TestTickets(unittest.TestCase):
    """Tickets in the reader's form."""

    def test_c17_a_ticket_over_the_p90_needs_a_ruling(self) -> None:
        """Over the p90 with no ruling is refused; within it, or with one, is filed."""
        hub = made(GIVEN)
        over = refusal(hub, "ticket", max_lines="3000", **TICKET)
        assert_that(over, contains_string("p90"))
        within = act(GIVEN, hub, "ticket", max_lines="400", **TICKET)
        ruled = act(GIVEN, hub, "ticket", max_lines="3000", ruling="#5", **TICKET)
        assert_that((within.isdigit(), ruled.isdigit()), equal_to((True, True)))
        pathless = refusal(hub, "ticket", max_lines="10", **{**TICKET, "paths": ""})
        assert_that(pathless, contains_string("paths"))


class TestOverride(unittest.TestCase):
    """Overrides lift one line, never a failed check."""

    def test_c17_a_failed_check_is_not_overridden(self) -> None:
        """A check line is refused."""
        world = red()
        line = stop_line(world, "check ")
        said = refusal(made(GIVEN, world), "override", stop=line, reason="known flake")
        assert_that(said, contains_string("not overridable"))

    def test_c17_a_diff_stop_is_lifted_by_its_override(self) -> None:
        """The record lifts that one line for that head."""
        world = change(ctx={"files": [BIG]})
        line = stop_line(world, "diff:")
        hub = made(GIVEN, world)
        said = refusal(
            hub, "override", stop="no such line", reason="owner ruling quire#1200"
        )
        assert_that(said, contains_string("not a stop"))
        why = "owner ruling quire#1200: the generated table counts"
        act(GIVEN, hub, "override", stop=line, reason=why)
        act(GIVEN, hub, "merge")
        assert_that(kinds(hub)[-1], equal_to("merge"))


class TestHolds(unittest.TestCase):
    """A hold refuses only its scope, in its repository."""

    def test_c17_update_branch_under_a_hold_is_refused(self) -> None:
        """A hold of all scopes refuses update-branch."""
        hub = made(GIVEN)
        act(GIVEN, hub, "update-branch")
        hub.hub.issues_made[(REPO, 900)] = hold_issue(900, "all")
        assert_that(refusal(hub, "update-branch"), contains_string("hold"))
        act(GIVEN, hub, "unhold", number="900")
        act(GIVEN, hub, "update-branch")
        assert_that(
            kinds(hub), equal_to(["update-branch", "close-issue", "update-branch"])
        )

    def test_c17_a_hold_of_another_repository_holds_nothing_here(self) -> None:
        """A hold of every scope in another repository leaves this one's merge alone."""
        hub = fakehub.made(BASE, GIVEN.controls, None, [REPO, "bats-lang/pwa"])
        hub.hub.issues_made[("bats-lang/pwa", 902)] = hold_issue(902, "all")
        act(GIVEN, hub, "merge")
        assert_that(kinds(hub), equal_to(["merge"]))

    def test_c17_a_hold_of_another_scope_holds_nothing_here(self) -> None:
        """An undraft hold leaves merge alone; a title-only edit checks no body."""
        hub = made(GIVEN)
        hub.hub.issues_made[(REPO, 901)] = hold_issue(901, "undrafts")
        act(GIVEN, hub, "merge")
        act(GIVEN, hub, "pr-edit", title="a new title")
        assert_that(kinds(hub), equal_to(["merge", "pr-edit"]))

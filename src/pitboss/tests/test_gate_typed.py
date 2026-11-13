"""The gate's rows on typed state made by hand (plan 6.1, keyword: gate).

The rows read only what ``pullstate`` typed; each test here changes one value of a
hand-made state and reads the stop it gives, with no JSON.
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import gate, gateevents, gatefields, gatepolicy, gaterows, totalbody
from .. import totalchecks
from ..gatestop import Route, Stop
from ..pullrecords import File, GateState, Hold, Mistyped, Ticket, Unread
from . import gatestate

SCHEMA = {"title": "string", "milestone": "object | null"}
POLICY = gatepolicy.Policy(
    schema=SCHEMA,
    review=lambda review, head, body, tickets: "",
    plan=lambda review, body: "",
)
OPEN = Ticket(state="open", reason="None", locked=False, is_pull=False, body="")
RUNNING = dataclasses.replace(
    gatestate.GREEN_RUN, status="in_progress", conclusion="None", number=2
)
RED = dataclasses.replace(gatestate.GREEN_RUN, name="lint", conclusion="failure")


def _says(found: Sequence[Stop], lines: Sequence[str]) -> None:
    # the stops' lines are these, in order
    assert_that([each.line for each in found], equal_to(list(lines)))


def _routed(found: Sequence[Stop]) -> Sequence[Route]:
    return [each.route for each in found]


def _gated(action: str, made: GateState) -> Sequence[Stop]:
    return gate.stops_for(action, gate.Gate(state=made), POLICY)


def _ticket(**changes: object) -> Ticket:
    return dataclasses.replace(OPEN, **changes)  # type: ignore[arg-type]


class TestAlone(unittest.TestCase):
    """An input not given, or a list of another shape, is the only stop (6.1)."""

    def test_6_1_an_input_not_given_is_alone(self) -> None:
        """No row runs when an input is absent."""
        found = _gated("merge", gatestate.state(absent=["repo"]))
        _says(found, ["input repo: not read (no input has a default)"])

    def test_6_1_a_list_of_another_shape_is_alone(self) -> None:
        """A conclusion of another type is the schema stop and nothing else."""
        reads = gatestate.lists_of(runs=Mistyped(name="conclusion", said="[5]"))
        found = _gated("merge", gatestate.state(reads=reads))
        said = "(check_runs: conclusion=[5])"
        _says(found, [f"input: the response is not of GitHub's schema {said}"])

    def test_6_1_a_list_github_refused_is_a_stop(self) -> None:
        """An error GitHub answered is a stop of its own, the rows still run."""
        reads = gatestate.lists_of(files=Unread(why="Not Found"))
        found = gaterows.read_stops(gatestate.state(reads=reads))
        _says(found, ["input files: GitHub answered Not Found"])


class TestRows(unittest.TestCase):
    """One value changed, one stop (6.1)."""

    def test_6_1_a_clean_change_goes(self) -> None:
        """The hand-made state with its ticket has no stop."""
        made = gatestate.state(tickets={"#1": OPEN})
        assert_that(_gated("merge", made), equal_to([]))

    def test_6_1_no_ticket(self) -> None:
        """A change that closes nothing."""
        found = _gated("merge", gatestate.state())
        assert_that(_routed(found), equal_to([Route.NO_TICKET]))

    def test_6_1_each_ticket_line(self) -> None:
        """Unread, a pull request, closed, locked, open."""
        tickets = {
            "#1": Unread(why="gone"),
            "#2": _ticket(is_pull=True),
            "#3": _ticket(state="closed", reason="completed"),
            "#4": _ticket(locked=True),
            "#5": OPEN,
        }
        found = gaterows.ticket_stops(gatestate.state(tickets=tickets))
        lines = [
            "ticket #1: not read (gone)",
            "ticket #2: a pull request, not an issue",
            "ticket #3: closed (completed)",
            "ticket #4: locked",
        ]
        _says(found, lines)

    def test_6_1_a_running_and_a_red_check(self) -> None:
        """A running check stops a merge only; a red one stops an undraft too."""
        made = gatestate.state(reads=gatestate.lists_of(runs=[RUNNING, RED]))
        got = [
            _routed(gaterows.check_stops(action, made))
            for action in ("merge", "undraft")
        ]
        assert_that(got, equal_to([[Route.RUNNING, Route.RED], [Route.RED]]))

    def test_6_1_a_hold(self) -> None:
        """A hold of all actions stops a merge."""
        made = gatestate.state(holds=[Hold(title="freeze", scope="all")])
        _says(gaterows.hold_stops("merge", made), ["hold: freeze holds all"])

    def test_6_1_an_open_blocker(self) -> None:
        """A blocker that is not closed."""
        made = gatestate.state(blockers={"#9": "open", "#8": "closed"})
        _says(gaterows.body_stops(made, POLICY), ["blocked: #9, which is open"])

    def test_6_1_a_paused_pr_armed_and_a_formal_request(self) -> None:
        """Changes requested, and auto-merge on a paused PR."""
        merging = gatestate.merge_fields(auto_merge=True, labels=["paused-owner"])
        timeline = [gatestate.happened("reviewed", state="changes_requested")]
        made = gatestate.state(
            pull=gatestate.pull_of(merging=merging),
            reads=gatestate.lists_of(timeline=timeline),
        )
        found = _routed(gaterows.merge_stops("merge", made))
        assert_that(found, equal_to([Route.CHANGES_REQUESTED, Route.PAUSED]))
        assert_that(gaterows.merge_stops("undraft", made), equal_to([]))

    def test_6_1_the_diff(self) -> None:
        """Added markup lines, a change over its Max-lines, a workflow not linted."""
        files = [
            File(name="README.md", additions=2, deletions=0),
            File(name=".github/workflows/ci.yml", additions=200, deletions=0),
        ]
        made = gatestate.state(reads=gatestate.lists_of(files=files, statuses=[]))
        found = _routed(gaterows.diff_stops("merge", made, "change"))
        assert_that(
            found, equal_to([Route.ADDED_LINES, Route.MAX_LINES, Route.WORKFLOW])
        )

    def test_6_1_a_review_stop_by_action(self) -> None:
        """No attempt stops a merge and an undraft; other actions have no row."""
        made = gatestate.state(reads=gatestate.lists_of(timeline=[]))
        lines = [
            [each.line for each in gaterows.review_stops(action, made, POLICY)]
            for action in ("merge", "undraft", "close")
        ]
        none = ["review: no review attempt on this PR"]
        assert_that(lines, equal_to([none, none, []]))


class TestKind(unittest.TestCase):
    """A PR's kind from its branch and the names of its files (6.1)."""

    def test_6_1_kinds(self) -> None:
        """A publish, a relock, a change, and no files."""
        archive = ["pkg/json_2026.11.1.0.bats", "pkg/json_2026.11.1.0.bats.sha256"]
        kinds = [
            totalbody.kind("publish/json", archive),
            totalbody.kind("relock/2026-11-01", ["bats.lock"]),
            totalbody.kind("relock/2026-11-01", ["src/a.py"]),
            totalbody.kind("publish/json", []),
        ]
        assert_that(kinds, equal_to(["publish", "relock", "change", "change"]))

    def test_6_1_kind_of_reads_the_head_branch(self) -> None:
        """The state's head branch and files decide it."""
        files = [File(name="bats.lock", additions=1, deletions=1)]
        place = gatestate.place_of(head_ref="relock/2026-11-01")
        made = gatestate.state(
            pull=gatestate.pull_of(where=place),
            reads=gatestate.lists_of(files=files),
        )
        assert_that(gaterows.kind_of(made), equal_to("relock"))


class TestChecks(unittest.TestCase):
    """The newest run of each name (6.1)."""

    def test_6_1_an_older_run_listed_later_is_not_current(self) -> None:
        """Order in the list does not decide; the start time does."""
        newer = dataclasses.replace(gatestate.GREEN_RUN, started_at="2026-11-02")
        runs = [newer, dataclasses.replace(RED, name="check")]
        assert_that(list(totalchecks.current_runs(runs)), equal_to([newer]))


class TestFields(unittest.TestCase):
    """A field's row on typed state (6.1)."""

    def test_6_1_a_mistyped_field_no_rule_names(self) -> None:
        """A milestone of another type is said so."""
        made = gatestate.pull_of(
            said={"title": "the change", "milestone": "5"},
            breaks=[Mistyped(name="milestone", said="5")],
        )
        found = gatefields.field_stops(gatestate.state(pull=made), "merge", SCHEMA)
        _says(found, ["milestone=5: not of the documented type"])

    def test_6_1_a_required_field_absent(self) -> None:
        """A title not given: no text, and absent."""
        made = gatestate.state(pull=gatestate.pull_of(title_is_text=False, said={}))
        found = gatefields.field_stops(made, "merge", {"title": "required, string:"})
        _says(found, ["title=None: not text", "title: a required field is absent"])


class TestEvents(unittest.TestCase):
    """The events since the newest review (6.1)."""

    def test_6_1_events_after_the_review(self) -> None:
        """A known label and a benign event pass; an unknown label and a push stop."""
        timeline = [
            gatestate.happened("committed"),
            gatestate.REVIEW,
            gatestate.happened("labeled", label="dependencies"),
            gatestate.happened("labeled", label="mine"),
            gatestate.happened("commented"),
            gatestate.happened("head_ref_force_pushed_again"),
        ]
        made = gatestate.state(reads=gatestate.lists_of(timeline=timeline))
        found = gateevents.event_stops(made, gatepolicy.BENIGN_EVENTS)
        assert_that(_routed(found), equal_to([Route.LABEL, Route.REVIEW]))

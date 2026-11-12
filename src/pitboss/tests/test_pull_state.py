"""Every open PR has a line in ``slots next``, a failed status says why (#162).

The cause: a commit status that failed (``text-lint``) was never read, and a
PR that is offered for no round (it waits for CI, the owner or a ruling) had no
line at all, so the sweep named nothing that blocked it.
"""

import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, has_item

from . import fakes, test_flow_sweep, world
from .test_commands import sweep
from .test_slot_commands import next_output

HEAD = test_flow_sweep.HEAD
PATHS = {
    kind: fakes.page(f"{world.PROJECT}/commits/{HEAD}/{kind}")
    for kind in ("status", "check-runs")
}
RUN = "https://github.com/owner/project/actions/runs/5"
REVIEW_WORDS = "review it (a reviewer that is not its author)"
# keyword: finish-partial: a red text-lint status on a PR to review is finished first
FINISH_WORDS = (
    "finish the PR a worker handed back unfinished: the `text-lint` status of the"
    " head is red (first-line): fix the body"
)
BOT = {"login": "tool[bot]"}
PASSED = {
    "id": 9,
    "name": "text-lint",
    "status": "completed",
    "conclusion": "success",
    "completed_at": "2026-10-31T00:00:00Z",
}
WAITING = {"id": 9, "name": "t", "status": "in_progress", "conclusion": None}


def status(
    state: str, description: str = "", context: str = "text-lint"
) -> Mapping[str, str]:
    """One commit status as the API gives it.

    Args:
        state: its state.
        description: its description.
        context: its context.

    Returns:
        The JSON.
    """
    return {
        "context": context,
        "state": state,
        "description": description,
        "target_url": RUN,
        "created_at": "2026-10-30T00:00:00Z",
    }


def with_statuses(
    statuses: Sequence[Mapping[str, str]], **changes: object
) -> world.World:
    """A world whose PR 3 has the commit statuses.

    Args:
        statuses: the statuses of PR 3's head.
        **changes: changes to PR 3's JSON.

    Returns:
        The world.
    """
    here = test_flow_sweep.world_with([], **changes)
    here.bodies[PATHS["status"]] = {"statuses": list(statuses)}
    return here


def lines_of(out: str, marker: str) -> Sequence[str]:
    """The lines of an output that are about PR 3 and start with a marker.

    Args:
        out: the output.
        marker: the marker.

    Returns:
        The lines.
    """
    return [
        each
        for each in out.splitlines()
        if each.startswith(marker) and "owner/project#3" in each
    ]


def blocked_of(here: world.World) -> Sequence[str]:
    """PR 3's BLOCKED lines in ``slots next``.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    return lines_of(next_output(here), "BLOCKED")


def blocked_failure(**changes: object) -> str:
    """The BLOCKED line of PR 3, whose ``text-lint`` status failed.

    Args:
        **changes: changes to PR 3's JSON.

    Returns:
        The line.
    """
    return blocked_of(with_statuses([status("failure")], **changes))[0]


LINK = "https://github.com/owner/pwa/issues/278"


def blocked_with_ticket(
    state: str, description: str = "", labels: Sequence[Mapping[str, str]] = ()
) -> str:
    """The BLOCKED line of PR 3 when ticket owner/pwa#278 exists.

    Args:
        state: the ticket's state.
        description: the failed status's description.
        labels: the labels of PR 3.

    Returns:
        The line.
    """
    here = with_statuses([status("failure", description)], labels=list(labels))
    here.bodies["repos/owner/pwa/issues/278"] = {"state": state, "labels": []}
    return blocked_of(here)[0]


class TestDraftWithAFailedStatus(unittest.TestCase):
    """A draft PR with a failing status and no review (Done-when 2)."""

    def test_it_has_a_state_line_and_a_blocked_line(self) -> None:
        """The PR is never absent: its next step, and what blocks it."""
        out = next_output(with_statuses([status("failure", "first-line")], draft=True))
        assert_that(
            lines_of(out, "PR STATE"),
            equal_to([f"PR STATE owner/project#3: draft next step: {FINISH_WORDS}"]),
        )
        blocked = lines_of(out, "BLOCKED")
        assert_that(len(blocked), equal_to(1))
        assert_that(blocked[0], contains_string("status text-lint failure"))
        assert_that(blocked[0], contains_string(f"({RUN})"))

    def test_the_sweep_names_the_blocked_pr_too(self) -> None:
        """The same line, in the PR's lines of the sweep."""
        here = with_statuses([status("failure")], draft=True)
        assert_that(len(lines_of(sweep(here).out, "BLOCKED")), equal_to(1))

    def test_only_a_failure_or_an_error_blocks(self) -> None:
        """A passing or a pending status blocks nothing."""
        counts = {
            state: len(blocked_of(with_statuses([status(state)], draft=True)))
            for state in ("success", "pending", "failure", "error")
        }
        assert_that(
            counts, equal_to({"success": 0, "pending": 0, "failure": 1, "error": 1})
        )


class TestTheCauseOfATextLintFailure(unittest.TestCase):
    """Done-when 3: the body or the pin."""

    def test_a_body_that_does_not_lint_is_a_body_finding(self) -> None:
        """The first finding is named, and the fix is the body's."""
        blocked = blocked_failure(draft=True)
        assert_that(blocked, contains_string("is about the BODY of the PR"))
        assert_that(blocked, contains_string("fix the body"))

    def test_a_body_that_lints_is_a_pin_finding(self) -> None:
        """A bot's PR is exempt from the lint, so its failure is the tool's."""
        blocked = blocked_failure(user=BOT)
        assert_that(blocked, contains_string("is about the PIN, not the body"))
        assert_that(blocked, contains_string("edit no body"))
        assert_that(blocked, contains_string("before pitboss#171"))
        assert_that(blocked, contains_string("grant pull-requests: read"))

    def test_a_relock_branch_failure_is_the_pins(self) -> None:
        """The lint makes a relock branch exempt, as it does a bot."""
        head = {"sha": HEAD, "ref": "relock/2026-11-04"}
        blocked = blocked_failure(head=head)
        assert_that(blocked, contains_string("is about the PIN, not the body"))

    def test_another_context_says_no_cause(self) -> None:
        """Only text-lint's cause is told."""
        here = with_statuses([status("failure", context="other")], draft=True)
        words = blocked_of(here)[0].split()
        assert_that({"BODY", "PIN"} & set(words), equal_to(set()))

    def test_an_open_ticket_the_description_names_is_linked(self) -> None:
        """Row 1: the link of the open ticket, and where it was named."""
        found = blocked_with_ticket("open", description="stale pin, see owner/pwa#278")
        assert_that(found, contains_string(f"blocked by the open ticket {LINK}"))
        assert_that(found, contains_string("(named by the status description)"))

    def test_a_closed_ticket_the_description_names_is_not_shown(self) -> None:
        """Row 1: only an open ticket is a blocker."""
        found = blocked_with_ticket(
            "closed", description="stale pin, see owner/pwa#278"
        )
        assert_that("blocked by" in found, equal_to(False))

    def test_a_label_of_the_pr_that_names_a_ticket_is_linked(self) -> None:
        """Row 1: a label names the open ticket."""
        label = {"name": "waiting for owner/pwa#278"}
        found = blocked_with_ticket("open", labels=[label])
        assert_that(found, contains_string(f"blocked by the open ticket {LINK}"))
        assert_that(found, contains_string("named by the label waiting for"))

    def test_a_label_of_the_ticket_the_pr_fixes_is_linked(self) -> None:
        """Row 1: the label of the ticket the PR fixes names another ticket."""
        here = with_statuses([status("failure")], body="Fixes owner/pwa#5\n")
        label = {"name": "blocked by owner/pwa#278"}
        here.bodies["repos/owner/pwa/issues/5"] = {
            "number": 5,
            "title": "T",
            "created_at": "2026-10-01T00:00:00Z",
            "body": "",
            "state": "open",
            "labels": [label],
        }
        here.bodies["repos/owner/pwa/issues/278"] = {"state": "open", "labels": []}
        found = blocked_of(here)[0]
        assert_that(found, contains_string(f"blocked by the open ticket {LINK}"))
        assert_that(found, contains_string("of owner/pwa#5)"))

    def test_a_ticket_that_cannot_be_read_is_not_shown(self) -> None:
        """Neither the fixed ticket nor the named one answers."""
        here = with_statuses(
            [status("failure", "see owner/pwa#278")], body="Fixes owner/pwa#5\n"
        )
        assert_that("blocked by" in blocked_of(here)[0], equal_to(False))

    def test_the_same_status_on_other_prs_is_said(self) -> None:
        """A status that fails on every PR is the pin's."""
        here = with_statuses([status("failure")])
        here.bodies[world.HEAD_STATUS] = {"statuses": [status("failure")]}
        blocked = blocked_of(here)[0]
        assert_that(blocked, contains_string("the same status fails on"))
        assert_that(blocked, contains_string("owner/project#2"))


class TestEveryPrHasALine(unittest.TestCase):
    """Done-when 1: a PR is never absent."""

    def test_every_open_pr_has_a_state_line(self) -> None:
        """PR 1, 2, 3 and the library's PR 4, whatever their steps."""
        out = next_output(world.make_world())
        states = [x for x in out.splitlines() if x.startswith("PR STATE")]
        for each in ("project#1", "project#2", "project#3", "lib#4"):
            assert_that(
                any(f"owner/{each}:" in line for line in states), equal_to(True)
            )

    def test_a_head_waiting_for_ci_says_so(self) -> None:
        """A running check is waiting for CI at this head."""
        here = test_flow_sweep.world_with([])
        here.bodies[PATHS["check-runs"]] = {"check_runs": [WAITING]}
        wanted = "PR STATE owner/project#3: next step: waiting for CI at this head"
        assert_that(lines_of(next_output(here), "PR STATE"), has_item(wanted))

    def test_a_pr_offered_for_a_round_names_the_round(self) -> None:
        """The words of its NEXT line."""
        wanted = f"PR STATE owner/project#3: next step: {REVIEW_WORDS}"
        out = next_output(world.make_world())
        assert_that(lines_of(out, "PR STATE"), has_item(wanted))


class TestAnsweredStatus(unittest.TestCase):
    """A failed status that a later passing check run of its name answers."""

    def test_a_later_passing_check_run_clears_it(self) -> None:
        """The newest answer is the pass."""
        here = with_statuses([status("failure")], draft=True)
        here.bodies[PATHS["check-runs"]] = {"check_runs": [PASSED]}
        assert_that(blocked_of(here), equal_to([]))

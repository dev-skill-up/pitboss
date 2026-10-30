"""End-to-end tests of ``pitboss next CONFIG TICKET`` (pitboss#107)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import steps
from . import fakes, world

BODY = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"
AFTER = ("--now", world.FUTURE)
THIRD = f"{world.PROJECT}/pulls/3"
JOBS = fakes.page(f"{world.PROJECT}/actions/runs/11/jobs")


def next_for(here: world.World, ticket: str) -> world.Result:
    """Run ``pitboss next`` on a ticket.

    Args:
        here: the world.
        ticket: the ticket.

    Returns:
        What it did.
    """
    return world.invoke(here, "next", here.config, ticket, *AFTER)


def said(found: world.Result) -> str:
    """What a command printed, without the note of the library the world cannot read.

    Args:
        found: what the command did.

    Returns:
        The other lines, each with its newline.
    """
    lines = [each for each in found.out.splitlines() if "owner/gone" not in each]
    return "".join(f"{each}\n" for each in lines)


def third(here: world.World, **changes: object) -> None:
    """Change PR 3 of a world (its body names ticket 7 and has a Plan and Execution).

    Args:
        here: the world.
        **changes: changes to its JSON.
    """
    changes = {"body": BODY, "head": {"sha": "3" * 40, "ref": "branch-3"}, **changes}
    here.bodies[THIRD] = fakes.pull_body(3, **changes)


def line(step: steps.Next, ticket: str, pull: str) -> str:
    """The line ``pitboss next`` prints.

    Args:
        step: the step.
        ticket: the ticket.
        pull: the PR.

    Returns:
        The line, with its newline.
    """
    return f"{step.step.name}: {ticket} ({pull}): {steps.describe(step)}\n"


class TestNext(unittest.TestCase):
    """The one step a ticket is at."""

    def test_a_pr_that_says_fixes_gets_its_step(self) -> None:
        """PR 3 is green with no review: a regular review of both."""
        here = world.make_world()
        third(here)
        found = next_for(here, "#7")
        step = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)
        expected = line(step, "owner/project#7", "owner/project#3")
        assert_that((said(found), found.code), equal_to((expected, 0)))

    def test_the_ticket_can_be_spelled_in_full_or_by_repository_name(self) -> None:
        """``owner/repo#N`` and ``repo#N`` name the same ticket."""
        here = world.make_world()
        third(here)
        found = [
            said(next_for(here, each)) for each in ("owner/project#7", "project#7")
        ]
        assert_that(found[0], equal_to(found[1]))

    def test_fixes_with_a_full_reference_in_another_repository(self) -> None:
        """A PR of the project can fix a ticket of a library."""
        here = world.make_world()
        third(here, body=BODY.replace("Fixes #7", "Fixes owner/lib#6"))
        found = next_for(here, "owner/lib#6")
        step = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)
        expected = line(step, "owner/lib#6", "owner/project#3")
        assert_that(said(found), equal_to(expected))

    def test_a_bare_number_means_the_ticket_of_the_pr_repository(self) -> None:
        """``Fixes #7`` in the library's PR is ``owner/lib#7``."""
        here = world.make_world()
        here.bodies["repos/owner/lib/pulls/4"] = fakes.pull_body(4, body=BODY)
        found = [
            said(next_for(here, each)) for each in ("owner/lib#7", "owner/project#7")
        ]
        assert_that(
            found[0].startswith("MERGE: owner/lib#7 (owner/lib#4)"), equal_to(True)
        )
        assert_that(found[1].startswith("WORKER: owner/project#7: "), equal_to(True))

    def test_a_longer_number_is_another_ticket(self) -> None:
        """``Fixes #70`` does not fix ticket 7."""
        here = world.make_world()
        third(here, body=BODY.replace("Fixes #7", "Fixes #70"))
        found = next_for(here, "#7")
        assert_that(
            said(found), equal_to(f"WORKER: owner/project#7: {steps.FIRST_STEP}\n")
        )

    def test_a_ticket_no_pr_fixes_starts_with_a_worker(self) -> None:
        """The first step is to write the code and the Plan and Execution body."""
        found = next_for(world.make_world(), "#99")
        assert_that(
            said(found), equal_to(f"WORKER: owner/project#99: {steps.FIRST_STEP}\n")
        )
        assert_that(found.code, equal_to(0))

    def test_a_pr_without_the_body_is_the_workers(self) -> None:
        """The worker writes the Plan and Execution body."""
        here = world.make_world()
        third(here, body="Fixes #7\n")
        found = next_for(here, "#7")
        step = steps.worker(steps.Task.FIRST_ROUND)
        assert_that(
            said(found), equal_to(line(step, "owner/project#7", "owner/project#3"))
        )

    def test_a_paused_pr_waits_for_the_owner(self) -> None:
        """The pause label is read from the PR."""
        here = world.make_world()
        third(here, labels=[{"name": "paused-owner"}])
        found = next_for(here, "#7")
        assert_that(
            said(found).startswith("WAIT_FOR_OWNER: owner/project#7"), equal_to(True)
        )

    def test_a_draft_is_undrafted_when_the_runners_are_quiet(self) -> None:
        """No job waits and the record shows the quiet period passed."""
        here = world.make_world()
        third(here, draft=True)
        here.bodies[JOBS] = {"jobs": []}
        record = here.clone / ".git" / "pitboss-pressure.log"
        record.write_text("2029-12-01T00:00:00+00:00 none\n")
        found = next_for(here, "#7")
        assert_that(said(found).startswith("UNDRAFT: owner/project#7"), equal_to(True))

    def test_a_draft_whose_record_cannot_be_read_is_not_undrafted(self) -> None:
        """A quiet period nobody could read is not one that was seen."""
        here = world.make_world()
        third(here, draft=True)
        here.bodies[JOBS] = {"jobs": []}
        (here.clone / ".git" / "pitboss-pressure.log").mkdir()
        found = next_for(here, "#7")
        step = steps.regular_review(steps.Stage.PLAN_ONLY)
        assert_that(
            said(found), equal_to(line(step, "owner/project#7", "owner/project#3"))
        )

    def test_a_draft_under_pressure_gets_a_plan_review(self) -> None:
        """A queue job waits, so the draft stays one."""
        here = world.make_world()
        third(here, draft=True)
        found = next_for(here, "#7")
        step = steps.regular_review(steps.Stage.PLAN_ONLY)
        assert_that(
            said(found), equal_to(line(step, "owner/project#7", "owner/project#3"))
        )

    def test_a_pr_with_an_unreadable_neighbour_is_not_a_ticket_without_a_pr(
        self,
    ) -> None:
        """A PR that could not be read may be the ticket's: no first step is printed."""
        here = world.make_world()
        world.unread_first(here)
        found = next_for(here, "#99")
        assert_that(found.code, equal_to(1))
        assert_that(
            said(found), contains_string("UNREADABLE owner/project#1: check-runs")
        )
        assert_that("WORKER" in said(found), equal_to(False))

    def test_a_pr_found_is_answered_whatever_else_is_unreadable(self) -> None:
        """The match decides, even with another PR unreadable."""
        here = world.make_world()
        world.unread_first(here)
        third(here)
        found = next_for(here, "#7")
        assert_that(found.code, equal_to(0))
        assert_that(
            said(found).startswith("REGULAR_REVIEW: owner/project#7"), equal_to(True)
        )

    def test_a_ticket_that_is_not_a_reference_is_refused(self) -> None:
        """Exit 2, and nothing is read."""
        here = world.make_world()
        found = [next_for(here, each) for each in ("seven", "#x", "")]
        codes = [each.code for each in found]
        assert_that(codes, equal_to([2, 2, 2]))
        assert_that(found[0].err, contains_string("owner/repo#N"))


class TestScan(unittest.TestCase):
    """The scan of the open PRs is read once for the run."""

    def test_each_pr_is_read_once(self) -> None:
        """Four open PRs, each one's details fetched once."""
        here = world.make_world()
        third(here)
        next_for(here, "#7")
        details: Sequence[str] = [
            call[-1]
            for call in here.calls
            if call[-1].startswith("repos/owner/")
            and "/pulls/" in call[-1]
            and call[-1].split("/")[-1].isdigit()
        ]
        assert_that(sorted(details), equal_to(sorted(set(details))))
        assert_that(len(details), equal_to(4))

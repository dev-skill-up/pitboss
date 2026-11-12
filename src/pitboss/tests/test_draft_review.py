"""A draft that needs a review or a fix is listed before any ticket (pitboss#156).

The cause: ``flow.draft_gate`` marked a draft ready as soon as the runners were
quiet, whether or not its Plan was approved, so the step was UNDRAFT, which is
offered for no round, and the slot went to a new ticket; and for a draft whose
head had a changes-needed review the gate asked for another Plan review instead
of the fix the review asked for.
"""

import dataclasses
import pathlib
import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to, starts_with

from .. import brief, shapes, steps
from . import fakes, test_flow, world
from .briefmake import has_none, make, text
from .test_commands import sweep
from .test_flow import CHANGES as FLOW_CHANGES, expect, state
from .test_flow_sweep import (
    APPROVED,
    CHANGES,
    HEAD,
    OLDER,
    graded,
    listed_for_third,
    world_with,
)
from .test_slot_commands import next_output

TICKET_LINE = re.compile(r"^NEXT \d+\. \S+#\d+ \(start a PR", re.MULTILINE)
THIRD_LINE = re.compile(
    r"^NEXT \d+\. owner/project#3 \((review it|[^,(]*)", re.MULTILINE
)
CI_LINE = "CI: first read the checks of the head SHA above"


def quiet(here: world.World) -> world.World:
    """Make the runners quiet, so an undraft is allowed now.

    Args:
        here: the world.

    Returns:
        The same world.
    """
    parts = (world.PROJECT, "actions", "runs", "11", "jobs")
    jobs = fakes.page("/".join(parts))
    here.bodies[jobs] = {"jobs": []}
    pathlib.Path(here.clone, ".git", "pitboss-pressure.log").write_text(
        "2029-12-01T00:00:00+00:00 none\n"
    )
    return here


def without_checks() -> world.World:
    """A world whose ready PR 3 has no check run at its head.

    Returns:
        The world.
    """
    here = world_with([])
    runs = fakes.page(f"{world.PROJECT}/commits/{HEAD}/check-runs")
    here.bodies[runs] = {"check_runs": []}
    return here


def listed(here: world.World) -> tuple[str, bool]:
    """PR 3's kind in ``slots next``, and whether it comes before every ticket.

    Args:
        here: the world.

    Returns:
        The words of its line (empty when none) and the order.
    """
    out = next_output(here)
    found = THIRD_LINE.search(out)
    ticket = TICKET_LINE.search(out)
    if found is None or ticket is None:
        return (found.group(1) if found else ""), False
    return found.group(1), found.start() < ticket.start()


class TestDraftsInSlotsNext(unittest.TestCase):
    """Each draft is listed, first, with the kind its step names."""

    def test_a_draft_with_no_review_is_listed_before_a_ticket(self) -> None:
        """Review none, the runners busy."""
        assert_that(listed(world_with([], draft=True)), equal_to(("review it", True)))

    def test_a_draft_with_no_review_is_listed_when_the_runners_are_quiet(
        self,
    ) -> None:
        """The cause: it was UNDRAFT, which no slot takes."""
        here = quiet(world_with([], draft=True))
        assert_that(listed(here), equal_to(("review it", True)))

    def test_a_draft_with_a_review_of_an_older_head_is_listed(self) -> None:
        """Older-head, after a merge of the base or a revision of the plan."""
        rounds = [graded(CHANGES, None, 1, sha=OLDER)]
        here = quiet(world_with(rounds, draft=True))
        assert_that(listed(here), equal_to(("review it", True)))

    def test_t132_a_draft_whose_plan_is_rejected_at_its_head_is_a_fix(self) -> None:
        """Changes needed on the Plan: revise the plan, before any ticket."""
        here = quiet(world_with([graded(CHANGES, None, 1)], draft=True))
        assert_that(listed(here), equal_to(("revise the plan", True)))

    def test_a_draft_with_changes_needed_at_its_head_is_a_ruling_not_a_line(
        self,
    ) -> None:
        """Changes needed on the Execution: Opus rules first, no NEXT line."""
        here = quiet(world_with([graded(None, CHANGES, 1)], draft=True))
        assert_that(listed(here), equal_to(("", False)))

    def test_a_draft_with_the_plan_approved_and_changes_needed_is_a_ruling(
        self,
    ) -> None:
        """pitboss#176, #390: the ruling is owed first, quiet or busy."""
        rounds = [graded(APPROVED, None, 1, sha=OLDER), graded(None, CHANGES, 2)]
        busy = world_with(rounds, draft=True)
        for here in (busy, quiet(world_with(rounds, draft=True))):
            assert_that(listed(here), equal_to(("", False)))

    def test_a_draft_with_the_plan_approved_is_not_a_review(self) -> None:
        """It is refused a review: its NEXT line is the hold on its undraft (#273)."""
        approved = graded(APPROVED, None, 1)
        words = listed(world_with([approved], draft=True))[0]
        assert_that(words, starts_with("HOLD on undrafts"))

    def test_a_pr_waiting_for_ci_has_no_next_line(self) -> None:
        """No round and no ready line: the order is unknown."""
        assert_that(listed(without_checks()), equal_to(("", False)))

    def test_a_draft_with_the_plan_approved_is_undrafted_when_quiet(self) -> None:
        """The undraft is no round: its NEXT line is the action itself (#273)."""
        approved = graded(APPROVED, None, 1)
        here = quiet(world_with([approved], draft=True))
        assert_that(listed(here)[0], starts_with("mark the PR ready"))
        assert_that(sweep(here).out, contains_string("owner/project#3"))


def swept(rounds: Sequence[shapes.Comment], **changes: object) -> str:
    """What the sweep prints for PR 3.

    Args:
        rounds: PR 3's comments.
        **changes: changes to PR 3's JSON.

    Returns:
        The sweep's output.
    """
    return sweep(world_with(rounds, **changes)).out


class TestDraftsInTheSweep(unittest.TestCase):
    """The sweep prints the instruction, not only the review column."""

    def test_the_sweep_says_what_a_draft_needs(self) -> None:
        """One DRAFT ROUND line, in place of WAIT-FOR-CI."""
        out = swept([], draft=True)
        assert_that(out, contains_string("DRAFT ROUND owner/project#3: review it"))
        assert_that(out, contains_string("it is listed first in `slots next`"))
        assert_that("WAIT-FOR-CI owner/project#3" in out, equal_to(False))

    def test_the_sweep_says_the_fix_of_a_rejected_draft(self) -> None:
        """The same words as the list; busy runners, so no second Plan review.

        pitboss#130: the world is not ``quiet``, so ``undraft_clear`` is false.
        """
        out = swept([graded(CHANGES, None, 1)], draft=True)
        assert_that(out, contains_string("DRAFT ROUND owner/project#3: revise the"))
        assert_that("DRAFT ROUND owner/project#3: review it" in out, equal_to(False))

    def test_t132_slots_next_sends_a_twice_rejected_draft_to_opus_while_busy(
        self,
    ) -> None:
        """pitboss#130: ``slots next`` offers a ruling, and no review line for PR 3."""
        rounds = [graded(CHANGES, None, 1, sha=OLDER), graded(CHANGES, None, 2)]
        here = world_with(rounds, draft=True)
        ruling = "make an Opus ruling: owner/project#3"
        assert_that(next_output(here), contains_string(ruling))
        assert_that(listed_for_third(here), equal_to([]))

    def test_a_draft_that_waits_for_its_undraft_has_no_round(self) -> None:
        """No round to offer, so no DRAFT ROUND line."""
        out = swept([graded(APPROVED, None, 1)], draft=True)
        assert_that("DRAFT ROUND" in out, equal_to(False))

    def test_a_ready_pr_without_a_check_run_is_not_a_draft_round(self) -> None:
        """It must still be refused a review: it waits for its CI."""
        out = sweep(without_checks()).out
        assert_that("DRAFT ROUND" in out, equal_to(False))
        assert_that(out, contains_string("WAIT-FOR-CI owner/project#3"))


class TestTheFlow(unittest.TestCase):
    """The draft gate, step by step."""

    def test_a_draft_is_not_undrafted_before_its_plan_is_approved(self) -> None:
        """Quiet runners, no review: the Plan review comes first."""
        draft = state(checks=(), draft=True, undraft_clear=True)
        expect(steps.regular_review(steps.Stage.PLAN_ONLY), draft)

    def test_a_draft_with_a_rejected_plan_is_revised(self) -> None:
        """The first rejection is the worker's, the runners quiet or busy.

        pitboss#130: with ``undraft_clear`` false the gate still reads the
        review; the step was a second Plan review of the same head.
        """
        review = test_flow.graded(*test_flow.PLAN_REJECTED, 1)
        for clear in (True, False):
            draft = state(review, checks=(), draft=True, undraft_clear=clear)
            expect(steps.worker(steps.Task.REVISE_PLAN), draft)

    def test_a_draft_rejected_twice_goes_to_opus(self) -> None:
        """pitboss#130: the second rejection is Opus's, not a third review."""
        rejections = (test_flow.FIRST_REJECTION, test_flow.SECOND_REJECTION)
        for clear in (True, False):
            draft = state(*rejections, checks=(), draft=True, undraft_clear=clear)
            expect(steps.opus_ruling(), draft)

    def test_a_draft_with_a_rejected_execution_gets_a_ruling(self) -> None:
        """Opus rules before any fix round."""
        review = test_flow.graded(None, FLOW_CHANGES, 1)
        expect(steps.opus_ruling(), state(review, draft=True))

    def test_a_draft_with_an_approved_plan_and_a_rejected_execution_is_ruled(
        self,
    ) -> None:
        """pitboss#176: the ruling comes before the undraft."""
        alone = test_flow.PLAN_APPROVED_ALONE
        approved = test_flow.graded(*alone, 1, sha=test_flow.OLDER)
        review = test_flow.graded(None, FLOW_CHANGES, 2)
        draft = state(approved, review, checks=(), draft=True, undraft_clear=True)
        expect(steps.opus_ruling(), draft)

    def test_a_draft_with_an_approved_plan_is_undrafted_when_quiet(self) -> None:
        """The undraft comes once the Plan is approved."""
        review = test_flow.graded(*test_flow.PLAN_APPROVED_ALONE, 1)
        draft = state(review, checks=(), draft=True, undraft_clear=True)
        expect(steps.undraft(), draft)


class TestTheBrief(unittest.TestCase):
    """The review of a draft says it has no check run."""

    def test_a_plan_review_reads_the_diff_and_the_body_only(self) -> None:
        """No hand-back NOT STARTED for a missing check run."""
        found = text(brief.Kind.REVIEW_PLAN)
        assert_that(found, contains_string("a draft runs no CI job"))
        assert_that(found, contains_string("You read the diff and the PR body only"))
        assert_that(found, contains_string("never hand back `NOT STARTED`"))
        has_none(
            found, ["CI: first read the checks", "the diff and the CI of the head"]
        )

    def test_a_plan_review_of_a_ready_pr_reads_the_checks(self) -> None:
        """A revised Plan of a PR that is not a draft has checks (pitboss#167)."""
        spec = dataclasses.replace(make(brief.Kind.REVIEW_PLAN), ready=True)
        found = brief.build(spec)
        assert_that(found.count(CI_LINE), equal_to(1))
        assert_that(found, contains_string("Scope (exclusive): the Plan of head"))
        has_none(
            found,
            [
                "a draft runs no CI job (its check is reported skipped, never missing; keyword: draft-ci, pitboss#321), so there is no CI"
            ],
        )

    def test_every_other_review_still_reads_the_checks(self) -> None:
        """A review of a head with a check run is refused without a finished one."""
        found = text(brief.Kind.REVIEW_FULL) + text(brief.Kind.REVIEW_EXECUTION)
        assert_that(found.count(CI_LINE), equal_to(2))
        has_none(
            found,
            [
                "a draft runs no CI job (its check is reported skipped, never missing; keyword: draft-ci, pitboss#321), so there is no CI"
            ],
        )

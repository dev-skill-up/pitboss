"""The top suggestions of ``next`` and ``slots next``, with their briefs (#118)."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import brieftextfix, suggest
from . import fakes, suggestions, test_flow_sweep, world
from .test_flow_sweep import APPROVED, CHANGES, HEAD, OLDER, graded, world_with
from .suggestions import (
    default_suggestions,
    kind_of_third,
    next_output,
    parsed,
    run_command,
    third,
    with_more_tickets,
)
from .says import errs

MERGE = {"sha": "2", "parents": [{"sha": "1"}, {"sha": "9"}]}
COMMENT_URL = "https://example.org/owner/project/pull/3#issuecomment-1"
RULING_URL = "https://example.org/owner/project/pull/3#issuecomment-2"


PLAN_ALONE = "review the Plan alone"


class TestOrderAndTruncation(unittest.TestCase):
    """Up to five, in the order the process ranks them."""

    def test_the_default_world_has_three_in_order(self) -> None:
        """A conflict, a review and a new ticket, each with its model class."""
        headers = [header for header, _ in default_suggestions()]
        assert_that(
            headers,
            equal_to(
                [
                    "SUGGESTION 1 of 3: resolve the conflict: owner/project#1:"
                    " slot, smallest model small",
                    "SUGGESTION 2 of 3: review the Plan and the Execution:"
                    " owner/project#3: slot, smallest model small",
                    "SUGGESTION 3 of 3: start a PR: owner/project#9:"
                    " slot, smallest model small",
                ]
            ),
        )

    def test_next_without_a_ticket_prints_what_slots_next_prints(self) -> None:
        """The same text, from either command."""
        here = world.make_world()
        found = run_command(here, "next")
        assert_that((found.out, found.code), equal_to((next_output(here), 0)))

    def test_exactly_five_say_nothing_more(self) -> None:
        """No count of what is not shown."""
        here = world.make_world()
        with_more_tickets(here, 2)
        output = next_output(here)
        assert_that(len(parsed(output)), equal_to(5))
        assert_that("more queued" in output, equal_to(False))

    def test_a_pr_that_waits_for_a_ruling_is_not_offered_twice(self) -> None:
        """After the ruling is recorded it is a worker round, and not a ruling."""
        here = world_with([*test_flow_sweep.RULED])
        assert_that("make an Opus ruling" in next_output(here), equal_to(False))

    def test_a_ticket_with_no_model_left_says_so(self) -> None:
        """Every model failed it."""
        here = world.make_world()
        for model in ("small", "large"):
            world.invoke(here, "slots", "failed", here.config, "#9", model)
        found = parsed(next_output(here))
        assert_that(
            found[-1][0].endswith("slot, smallest model none left"), equal_to(True)
        )


def merge_only(here: world.World) -> None:
    """Make PR 3's commits since the approved head a merge of the base.

    Args:
        here: the world.
    """
    authored = {"sha": "1", "parents": [{"sha": "0"}]}
    here.bodies[f"{world.PROJECT}/compare/main..." + HEAD] = {
        "commits": [authored, MERGE]
    }


def scope_is(here: world.World, kind: str, scope: str) -> None:
    """Check the kind of PR 3's review brief and how its scope line starts.

    Args:
        here: the world.
        kind: the kind, as the header says it.
        scope: the start of the third line of the brief.
    """
    header, brief = third(here)
    found = (header.split(": ")[1], brief[2][: len(scope)])
    assert_that(found, equal_to((kind, scope)))


def gate_project(here: world.World) -> None:
    """Make the project a gated repository.

    Args:
        here: the world.
    """
    path = pathlib.Path(here.config)
    path.write_text(path.read_text().replace('["gated"]', '["gated", "project"]'))


class TestKindsOfReview(unittest.TestCase):
    """The scope of a review follows the head and the review before it."""

    def test_a_first_review_is_the_full_review(self) -> None:
        """2b: no review of the PR."""
        scope = f"Scope: the full review of head {HEAD}"
        scope_is(world_with([]), "review the Plan and the Execution", scope)

    def test_a_merge_only_head_is_checked_for_the_merge_alone(self) -> None:
        """2a: approved at an older head, and the commits since are merges."""
        here = world_with([graded(APPROVED, APPROVED, 1, sha=OLDER)])
        merge_only(here)
        scope = (
            f"Scope (exclusive): this head {HEAD} differs from the approved"
            f" head {OLDER} only by a merge of main."
        )
        scope_is(here, "review the merge resolution only", scope)

    def test_a_head_changed_by_more_than_a_merge_is_reviewed_in_full(self) -> None:
        """2b: the same approval, but a commit of the author's since."""
        here = world_with([graded(APPROVED, APPROVED, 1, sha=OLDER)])
        scope_is(here, "review the Execution", f"Scope: the Execution of head {HEAD}")

    def test_the_review_after_a_fix_round_checks_its_findings(self) -> None:
        """2c: the review asked for changes, and the head moved."""
        here = world_with([graded(APPROVED, CHANGES, 1, sha=OLDER)])
        scope = (
            "Scope (exclusive): the fix round. The findings to check are"
            f" those of the newest review, of head {OLDER}."
        )
        scope_is(here, "review the fix round's findings only", scope)

    def test_a_revised_plan_is_graded_alone_not_as_a_fix(self) -> None:
        """A rejected Plan, revised: the head moved, the Plan was never approved."""
        here = world_with([graded(CHANGES, None, 1, sha=OLDER)])
        scope = f"Scope (exclusive): the Plan of head {HEAD}, alone,"
        scope_is(here, PLAN_ALONE, scope)

    def test_a_gated_merge_only_head_is_checked_for_the_merge_alone(self) -> None:
        """2a has no gated exception: the gate wants a review of this head."""
        here = world_with([graded(APPROVED, APPROVED, 1, sha=OLDER)])
        merge_only(here)
        gate_project(here)
        scope = (
            f"Scope (exclusive): this head {HEAD} differs from the approved"
            f" head {OLDER} only by a merge of main."
        )
        scope_is(here, "review the merge resolution only", scope)

    def test_a_gated_head_changed_by_more_than_a_merge_is_reviewed_in_full(
        self,
    ) -> None:
        """The gated repository is not special when the author changed the code."""
        here = world_with([graded(APPROVED, APPROVED, 1, sha=OLDER)])
        gate_project(here)
        scope_is(here, "review the Execution", f"Scope: the Execution of head {HEAD}")

    def test_a_draft_gets_the_plan_alone(self) -> None:
        """The Plan stage."""
        scope = f"Scope (exclusive): the Plan of head {HEAD}, alone,"
        scope_is(world_with([], draft=True), PLAN_ALONE, scope)


def with_addresses(here: world.World) -> world.World:
    """The world with the addresses of its review and its ruling set.

    Args:
        here: the world, whose PR 3 has a ruling and a review.

    Returns:
        The same world.
    """
    path = fakes.page("repos/owner/project/issues/3/comments")
    comment = here.bodies[path]
    assert isinstance(comment, list)
    comment[2]["html_url"] = COMMENT_URL
    comment[1]["html_url"] = RULING_URL
    return here


class TestKindsOfWork(unittest.TestCase):
    """The worker's rounds and their briefs."""

    def test_a_pr_without_the_body_is_the_first_round(self) -> None:
        """The Plan and Execution are written."""
        here = world_with([], body="Fixes #7\n")
        assert_that(kind_of_third(here), equal_to("write the Plan and Execution body"))

    def test_a_rejected_plan_is_revised(self) -> None:
        """The first Plan rejection, at this head."""
        here = world_with([graded(CHANGES, None, 1)])
        assert_that(kind_of_third(here), equal_to("revise the plan"))

    def test_a_rejected_execution_is_fixed_with_the_reviews_address(self) -> None:
        """The findings are in the review, whose address the brief gives."""
        header, brief = third(
            with_addresses(test_flow_sweep.unfixed_after_the_ruling())
        )
        assert_that(header.split(": ")[1], equal_to("fix the review"))
        task = (
            "Task: PR owner/project#3: fix the findings of the review at"
            f" {COMMENT_URL}, each one, and nothing else: make no change"
            " that no finding names. The Plan is approved: do not change it."
        )
        ruling = brieftextfix.RULING_NAMED.format(ruling=RULING_URL)
        for word, want in (("Task: ", task), ("Ruling: ", ruling)):
            assert_that([x for x in brief if x.startswith(word)], equal_to([want]))

    def test_an_approved_conflicted_head_is_resolved(self) -> None:
        """The base is merged in."""
        here = world_with([graded(APPROVED, APPROVED, 1)], mergeable_state="dirty")
        assert_that(kind_of_third(here), equal_to("resolve the conflict"))

    def test_a_conflict_is_resolved_and_a_ticket_is_started(self) -> None:
        """PR 1 (dirty, and red: the conflict first) and ticket 9 of the world."""
        found = default_suggestions()
        assert_that(
            found[0][1][1],
            contains_string("Task: PR owner/project#1 conflicts with main."),
        )
        assert_that(
            found[2][1][:2],
            equal_to(
                [
                    "Goal: ticket owner/project#9: A ticket",
                    "Task: do the whole of ticket owner/project#9 in one PR: write"
                    " the code, then open the PR.",
                ]
            ),
        )

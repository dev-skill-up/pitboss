"""The top suggestions of ``next`` and ``slots next``, with their briefs (#118)."""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import suggest
from . import fakes, test_flow_sweep, world
from .test_flow_sweep import APPROVED, CHANGES, HEAD, OLDER, graded, world_with
from .suggestions import (
    default_suggestions,
    next_output,
    parsed,
    run_command,
    third,
)

SUGGESTIONS = f"{world.PROJECT}/issues?state=open&labels=urgent"
MERGE = {"sha": "2", "parents": [{"sha": "1"}, {"sha": "9"}]}
COMMENT_URL = "https://example.org/owner/project/pull/3#issuecomment-1"


PLAN_ALONE = "review the Plan alone"


def with_more_tickets(here: world.World, count: int) -> None:
    """Add ``count`` more open tickets after the default one.

    Args:
        here: the world.
        count: how many.
    """
    more = [dict(world.TICKET, number=number) for number in range(10, 10 + count)]
    here.bodies[fakes.page(SUGGESTIONS)] = [world.TICKET, *more]


def kind_of_third(here: world.World) -> str:
    """The kind of PR 3's suggestion.

    Args:
        here: the world.

    Returns:
        The kind, as the header says it.
    """
    return third(here)[0].split(": ")[1]


class TestOrderAndTruncation(unittest.TestCase):
    """Up to five, in the order the process ranks them."""

    def test_the_default_world_has_three_in_order(self) -> None:
        """A red CI, a review and a new ticket, each with its model class."""
        headers = [header for header, _ in default_suggestions()]
        assert_that(
            headers,
            equal_to(
                [
                    "SUGGESTION 1 of 3: fix the CI: owner/project#1:"
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

    def test_next_without_a_ticket_needs_the_ledger(self) -> None:
        """The ledger is authoritative on the slots."""
        here = world.make_world()
        here.ledger.unlink()
        found = run_command(here, "next")
        assert_that((found.code, "LEDGER MISSING" in found.err), equal_to((1, True)))

    def test_more_than_five_are_cut_and_counted(self) -> None:
        """Five are shown; how many more are queued is said."""
        here = world.make_world()
        with_more_tickets(here, 5)
        output = next_output(here)
        headers = [header for header, _ in parsed(output)]
        assert_that(len(headers), equal_to(suggest.TOP))
        assert_that(
            headers[-1].startswith("SUGGESTION 5 of 5: start a PR"), equal_to(True)
        )
        assert_that(output, contains_string("SUGGESTION: 3 more queued, not shown\n"))

    def test_exactly_five_say_nothing_more(self) -> None:
        """No count of what is not shown."""
        here = world.make_world()
        with_more_tickets(here, 2)
        output = next_output(here)
        assert_that(len(parsed(output)), equal_to(5))
        assert_that("more queued" in output, equal_to(False))

    def test_nothing_queued_is_said(self) -> None:
        """No candidate: one line, no brief."""
        here = world.make_world()
        for path in (
            f"{world.PROJECT}/pulls?state=open",
            f"{world.LIBRARY}/pulls?state=open",
        ):
            here.bodies[fakes.page(path)] = []
        here.bodies[fakes.page(SUGGESTIONS)] = []
        output = next_output(here)
        assert_that(parsed(output), equal_to([]))
        assert_that(
            output,
            contains_string("SUGGESTION: none: nothing is queued that could start\n"),
        )

    def test_a_ruling_comes_first_and_takes_no_slot(self) -> None:
        """An Opus agent, before the list."""
        here = world_with(test_flow_sweep.TWO_PLAN_REJECTIONS)
        found = parsed(next_output(here))
        assert_that(
            found[0][0],
            equal_to(
                "SUGGESTION 1 of 3: make an Opus ruling: owner/project#3:"
                " Opus agent, no slot"
            ),
        )
        assert_that(
            found[0][1][0],
            equal_to("Goal: PR owner/project#3, which names no ticket: PR 3"),
        )
        assert_that(
            [header.split(": ")[2] for header, _ in found[1:]],
            equal_to(["owner/project#1", "owner/project#9"]),
        )

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

    def test_a_draft_gets_the_plan_alone(self) -> None:
        """The Plan stage."""
        scope = f"Scope (exclusive): the Plan of head {HEAD}, alone,"
        scope_is(world_with([], draft=True), PLAN_ALONE, scope)


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
        here = world_with([graded(APPROVED, CHANGES, 1)])
        path = fakes.page("repos/owner/project/issues/3/comments")
        comment = here.bodies[path]
        assert isinstance(comment, list)
        comment[0]["html_url"] = COMMENT_URL
        header, brief = third(here)
        assert_that(header.split(": ")[1], equal_to("fix the review"))
        task = [line for line in brief if line.startswith("Task: ")]
        assert_that(
            task,
            equal_to(
                [
                    "Task: PR owner/project#3: fix the findings of the review at"
                    f" {COMMENT_URL}, each one, and nothing else: make no change"
                    " that no finding names. The Plan is approved: do not change"
                    " it."
                ]
            ),
        )

    def test_an_approved_conflicted_head_is_resolved(self) -> None:
        """The base is merged in."""
        here = world_with([graded(APPROVED, APPROVED, 1)], mergeable_state="dirty")
        assert_that(kind_of_third(here), equal_to("resolve the conflict"))

    def test_a_red_ci_is_fixed_and_a_ticket_is_started(self) -> None:
        """PR 1 and ticket 9 of the default world."""
        found = default_suggestions()
        assert_that(
            found[0][1][1],
            contains_string(
                f"Task: PR owner/project#1: CI on the head {'1' * 40} is red."
            ),
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

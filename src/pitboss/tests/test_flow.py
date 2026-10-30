"""Tests for the review flow of a PR (keyword: review-flow, pitboss#107).

Each helper is tested alone on recorded PR data, and each row of the owner's
table goes through ``next_step``.
"""

import dataclasses
import json
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import config, flow, parsing, reviews, shapes
from . import fakes

HEAD = fakes.HEAD
OLDER = fakes.OLDER
SETTINGS = fakes.settings(fakes.directory())
FORM = SETTINGS.review.form
REVIEW = dataclasses.replace(
    SETTINGS.review,
    gated=frozenset({"owner/gated"}),
    trusted=frozenset({"MEMBER"}),
    gated_form=dataclasses.replace(FORM, lines=("## Gated review", *FORM.lines[1:])),
)
BODY = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nthe work\n"
GREEN = shapes.CheckRun(id=1, name="build", finished=True, failed=False)
RED = shapes.CheckRun(id=2, name="test", finished=True, failed=True)
RUNNING = shapes.CheckRun(id=3, name="lint", finished=False, failed=False)
CHANGES = "changes needed"
APPROVED = "approved"
Step = flow.Step
Task = flow.Task
Stage = flow.Stage


def comment(body: str, second: int, author: str = "MEMBER") -> shapes.Comment:
    """An issue comment.

    Args:
        body: its text.
        second: the second of the minute it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    return shapes.Comment(
        body=body,
        author_association=author,
        created_at=f"2026-10-30T00:00:{second:02d}Z",
    )


def graded(
    plan: str | None,
    execution: str | None,
    second: int,
    sha: str = HEAD,
    author: str = "MEMBER",
) -> shapes.Comment:
    """A review comment in the default form with the grades given.

    Args:
        plan: the plan grade, or None for no ``Plan:`` line.
        execution: the execution grade, or None for no ``Execution:`` line.
        second: the second of the minute it was written.
        sha: the head it reviewed.
        author: its author's association.

    Returns:
        The comment.
    """
    grades = [grade for grade in (plan, execution) if grade is not None]
    verdict = CHANGES if CHANGES in grades else APPROVED
    lines = [
        "## Review",
        f"Reviewed: {sha}",
        *([f"Plan: {plan}"] if plan else []),
        *([f"Execution: {execution}"] if execution else []),
        f"Verdict: {verdict}",
    ]
    return comment("\n".join(lines) + "\n", second, author)


def ruling(second: int, author: str = "MEMBER") -> shapes.Comment:
    """A recorded Opus ruling.

    Args:
        second: the second of the minute it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    return comment("Opus ruling\nRuling: do these steps\n", second, author)


def pull_of(**changes: object) -> shapes.Pull:
    """A PR as the API gives it, with a Plan and an Execution in its body.

    Args:
        **changes: changes to its JSON.

    Returns:
        The PR.
    """
    changes = {"body": BODY, **changes}
    return parsing.pull(json.dumps(fakes.pull_body(1, **changes)))


def state(
    *posted: shapes.Comment,
    slug: str = "owner/project",
    checks: Sequence[shapes.CheckRun] = (GREEN,),
    submitted: Sequence[shapes.PullReview] = (),
    clear: bool = False,
    **changes: object,
) -> flow.PullState:
    """The recorded data of one PR.

    Args:
        *posted: its issue comments.
        slug: its repository.
        checks: the check runs of its head.
        submitted: its GitHub reviews.
        clear: whether the runners allow an undraft now.
        **changes: changes to the PR's JSON.

    Returns:
        The state.
    """
    return flow.PullState(
        slug=slug,
        pull=pull_of(**changes),
        checks=checks,
        sources=reviews.Sources(comments=posted, reviews=submitted),
        review=REVIEW,
        undraft_clear=clear,
    )


def step_of(*posted: shapes.Comment, **kept: object) -> flow.Next:
    """The next step of a PR.

    Args:
        *posted: its issue comments.
        **kept: the rest of ``state``.

    Returns:
        The step.
    """
    return flow.next_step(state(*posted, **kept))  # type: ignore[arg-type]


PLAN_REJECTED = (CHANGES, None)
PLAN_APPROVED_ALONE = (APPROVED, None)
EXECUTION_REJECTED = (APPROVED, CHANGES)


class TestHelpers(unittest.TestCase):
    """Each helper alone, on recorded PR data."""

    def test_is_paused_for_owner(self) -> None:
        """The paused-owner label pauses a PR."""
        labelled = state(labels=[{"name": "paused-owner"}, {"name": "x"}])
        found = [flow.is_paused_for_owner(each) for each in (labelled, state())]
        assert_that(found, equal_to([True, False]))

    def test_has_plan_execution_body(self) -> None:
        """Both sections are needed, each as a heading of its own."""
        bodies = [BODY, "## Plan\nx\n", "## Execution\nx\n", "Plan and Execution", ""]
        found = [flow.has_plan_execution_body(state(body=each)) for each in bodies]
        assert_that(found, equal_to([True, False, False, False, False]))

    def test_is_draft_and_can_undraft(self) -> None:
        """A draft is the PR's flag; undrafting is the runners' say."""
        found = [
            flow.is_draft(state(draft=True)),
            flow.is_draft(state()),
            flow.can_undraft(state(clear=True)),
            flow.can_undraft(state()),
        ]
        assert_that(found, equal_to([True, False, True, False]))

    def test_has_conflict(self) -> None:
        """Only a dirty merge state is a conflict."""
        found = [
            flow.has_conflict(state(mergeable_state=each))
            for each in ("dirty", "clean", "behind")
        ]
        assert_that(found, equal_to([True, False, False]))

    def test_ci_result(self) -> None:
        """Green, red, or none while it runs or has not started."""
        cases = [
            ((GREEN,), flow.Ci.GREEN),
            ((GREEN, RED), flow.Ci.RED),
            ((RED, RUNNING), flow.Ci.RED),
            ((GREEN, RUNNING), None),
            ((), None),
            ((RUNNING,), None),
        ]
        found = [flow.ci_result(state(checks=checks)) for checks, _ in cases]
        assert_that(found, equal_to([expected for _, expected in cases]))

    def test_plan_approved(self) -> None:
        """Some regular review graded the plan approved, at any head."""
        approving = graded(*PLAN_APPROVED_ALONE, 1, sha=OLDER)
        rejecting = graded(*PLAN_REJECTED, 2)
        found = [
            flow.plan_approved(state(approving, rejecting)),
            flow.plan_approved(state(rejecting)),
            flow.plan_approved(state(graded(None, APPROVED, 1))),
            flow.plan_approved(state(graded(APPROVED, None, 1, author="NONE"))),
            flow.plan_approved(state()),
        ]
        assert_that(found, equal_to([True, False, False, False, False]))

    def test_plan_rejections_counts_regular_reviews(self) -> None:
        """Each regular review that graded the plan changes needed counts."""
        rejecting = [graded(*PLAN_REJECTED, second) for second in (1, 2)]
        github = shapes.PullReview(
            state="CHANGES_REQUESTED",
            commit_id=HEAD,
            author_association="MEMBER",
            submitted_at="2026-10-30T00:00:09Z",
        )
        found = [
            flow.get_plan_rejections(state()),
            flow.get_plan_rejections(state(rejecting[0])),
            flow.get_plan_rejections(state(*rejecting, graded(APPROVED, None, 3))),
            flow.get_plan_rejections(state(*rejecting, graded(None, CHANGES, 3))),
            flow.get_plan_rejections(state(rejecting[0], submitted=[github])),
            flow.get_plan_rejections(state(graded(*PLAN_REJECTED, 1, author="NONE"))),
        ]
        assert_that(found, equal_to([0, 1, 2, 2, 1, 0]))

    def test_opus_used(self) -> None:
        """A trusted comment whose first line is exactly ``Opus ruling``."""
        quoting = comment("I think the Opus ruling is", 2)
        found = [
            flow.opus_used(state(ruling(1))),
            flow.opus_used(state(ruling(1, author="NONE"))),
            flow.opus_used(state(quoting)),
            flow.opus_used(state()),
        ]
        assert_that(found, equal_to([True, False, False, False]))

    def test_execution_fixed_since_plan_approval(self) -> None:
        """An execution rejection with the plan approved on an older head."""
        first = graded(*EXECUTION_REJECTED, 1, sha=OLDER)
        again = graded(None, CHANGES, 2)
        before = graded(CHANGES, CHANGES, 1, sha=OLDER)
        found = [
            flow.execution_fixed_since_plan_approval(state(graded(*EXECUTION_REJECTED, 1))),
            flow.execution_fixed_since_plan_approval(state(first, again)),
            flow.execution_fixed_since_plan_approval(state(first)),
            flow.execution_fixed_since_plan_approval(state(before, again)),
            flow.execution_fixed_since_plan_approval(state(graded(*PLAN_REJECTED, 1))),
            flow.execution_fixed_since_plan_approval(state()),
        ]
        assert_that(found, equal_to([False, True, True, False, False, False]))

    def test_the_abbreviated_head_of_a_review_names_the_head(self) -> None:
        """A review names the head by a prefix of it too."""
        short = graded(*EXECUTION_REJECTED, 1, sha=HEAD[:7])
        again = graded(None, CHANGES, 2)
        found = flow.execution_fixed_since_plan_approval(state(short, again))
        assert_that(found, equal_to(False))

    def test_newest_counting_review(self) -> None:
        """The newest review of the current head, with its grades."""
        full = graded(APPROVED, CHANGES, 1)
        plain = graded(None, None, 2)
        older = graded(APPROVED, APPROVED, 3, sha=OLDER)
        github = shapes.PullReview(
            state="APPROVED",
            commit_id=HEAD,
            author_association="MEMBER",
            submitted_at="2026-10-30T00:01:00Z",
        )
        found = [
            flow.newest_counting_review(state(full)),
            flow.newest_counting_review(state(full, plain)),
            flow.newest_counting_review(state(full, older)),
            flow.newest_counting_review(state(older)),
            flow.newest_counting_review(state()),
            flow.newest_counting_review(state(full, submitted=[github])),
            flow.newest_counting_review(state(full, slug="owner/gated", submitted=[github])),
            flow.newest_counting_review(state(graded(CHANGES, None, 1))),
        ]
        grades = reviews.Verdict
        expected = [
            flow.Graded(sha=HEAD, plan=grades.APPROVED, execution=grades.CHANGES_NEEDED),
            flow.Graded(sha=HEAD, plan=None, execution=grades.APPROVED),
            flow.Graded(sha=HEAD, plan=grades.APPROVED, execution=grades.CHANGES_NEEDED),
            None,
            None,
            flow.Graded(sha=HEAD, plan=None, execution=grades.APPROVED),
            None,
            flow.Graded(sha=HEAD, plan=grades.CHANGES_NEEDED, execution=None),
        ]
        assert_that(found, equal_to(expected))

    def test_a_gated_repository_reads_the_strict_form(self) -> None:
        """Where gated, only the gated form with the full head counts."""
        gated = graded(*PLAN_REJECTED, 1)
        strict = dataclasses.replace(
            gated, body=gated.body.replace("## Review", "## Gated review")
        )
        found = [
            flow.get_plan_rejections(state(strict, slug="owner/gated")),
            flow.get_plan_rejections(state(gated, slug="owner/gated")),
            flow.get_plan_rejections(state(strict)),
        ]
        assert_that(found, equal_to([1, 0, 0]))


class TestTable(unittest.TestCase):
    """One test for each row of the owner's table."""

    def test_plan_rejected_the_first_time(self) -> None:
        """The worker revises the plan and changes no code."""
        found = step_of(graded(*PLAN_REJECTED, 1))
        assert_that(found, equal_to(flow.worker(Task.REVISE_PLAN)))

    def test_plan_rejected_the_second_time(self) -> None:
        """Opus rules."""
        found = step_of(graded(*PLAN_REJECTED, 1, sha=OLDER), graded(*PLAN_REJECTED, 2))
        assert_that(found, equal_to(flow.opus_ruling()))

    def test_plan_rejected_after_an_opus_ruling(self) -> None:
        """The owner decides."""
        found = step_of(
            graded(*PLAN_REJECTED, 1, sha=OLDER),
            graded(*PLAN_REJECTED, 2, sha=OLDER),
            ruling(3),
            graded(*PLAN_REJECTED, 4),
        )
        assert_that(found, equal_to(flow.pause_for_owner()))

    def test_plan_approved_execution_not_graded(self) -> None:
        """A review of the execution against the approved plan."""
        found = step_of(graded(*PLAN_APPROVED_ALONE, 1))
        expected = flow.regular_review(Stage.EXECUTION_AGAINST_PLAN)
        assert_that(found, equal_to(expected))

    def test_execution_rejected_by_the_review_that_approves_the_plan(self) -> None:
        """The worker fixes the execution."""
        found = step_of(graded(*EXECUTION_REJECTED, 1))
        assert_that(found, equal_to(flow.worker(Task.FIX_EXECUTION)))

    def test_execution_rejected_by_the_first_review_after_the_approval(self) -> None:
        """The worker fixes the execution."""
        found = step_of(graded(*PLAN_APPROVED_ALONE, 1), graded(None, CHANGES, 2))
        assert_that(found, equal_to(flow.worker(Task.FIX_EXECUTION)))

    def test_the_fixed_execution_rejected_again(self) -> None:
        """Opus rules."""
        found = step_of(
            graded(*EXECUTION_REJECTED, 1, sha=OLDER), graded(None, CHANGES, 2)
        )
        assert_that(found, equal_to(flow.opus_ruling()))

    def test_execution_rejected_after_an_opus_ruling(self) -> None:
        """The owner decides."""
        found = step_of(
            graded(*EXECUTION_REJECTED, 1, sha=OLDER), ruling(2), graded(None, CHANGES, 3)
        )
        assert_that(found, equal_to(flow.pause_for_owner()))

    def test_execution_approved_green_without_a_conflict(self) -> None:
        """Merge."""
        found = step_of(graded(APPROVED, APPROVED, 1))
        assert_that(found, equal_to(flow.merge()))


class TestFlow(unittest.TestCase):
    """The other branches of the flow, in the order written."""

    def test_a_paused_pr_waits_for_the_owner(self) -> None:
        """Before anything else."""
        found = step_of(labels=[{"name": "paused-owner"}], draft=True, body="")
        assert_that(found, equal_to(flow.wait_for_owner()))

    def test_no_plan_and_execution_body_is_the_first_work(self) -> None:
        """The worker writes the body, before any review or gate."""
        found = step_of(graded(*PLAN_REJECTED, 1), checks=(), body="")
        assert_that(found, equal_to(flow.worker(Task.FIRST_ROUND)))

    def test_a_draft_is_undrafted_when_it_can_be(self) -> None:
        """Before any CI wait or review."""
        found = step_of(draft=True, clear=True, checks=())
        assert_that(found, equal_to(flow.undraft()))

    def test_a_draft_whose_plan_is_not_approved_gets_a_plan_review(self) -> None:
        """No CI gate on a draft; the Plan only."""
        found = step_of(draft=True, checks=())
        assert_that(found, equal_to(flow.regular_review(Stage.PLAN_ONLY)))

    def test_a_draft_with_the_plan_approved_waits_for_the_window(self) -> None:
        """It cannot be undrafted yet."""
        found = step_of(graded(*PLAN_APPROVED_ALONE, 1), draft=True, checks=())
        assert_that(found, equal_to(flow.wait_for_undraft()))

    def test_nothing_runs_until_ci_finishes(self) -> None:
        """Nobody works or reviews while CI runs or has not started."""
        review = graded(*PLAN_REJECTED, 1)
        found = [step_of(review, checks=each) for each in ((), (RUNNING,), (GREEN, RUNNING))]
        assert_that(found, equal_to([flow.wait_for_ci()] * 3))

    def test_red_ci_goes_to_the_worker(self) -> None:
        """Even where a review stands."""
        found = step_of(graded(*PLAN_REJECTED, 1), checks=(RED,))
        assert_that(found, equal_to(flow.worker(Task.FIX_CI)))

    def test_red_ci_is_never_a_rejection(self) -> None:
        """It is not counted, and it does not move a plan to Opus."""
        posted = [graded(*PLAN_REJECTED, 1, sha=OLDER)]
        red = state(*posted, checks=(RED,))
        green = state(*posted, graded(*PLAN_REJECTED, 2))
        found = [
            flow.get_plan_rejections(red),
            flow.next_step(red),
            flow.get_plan_rejections(green),
            flow.next_step(green),
        ]
        expected = [1, flow.worker(Task.FIX_CI), 2, flow.opus_ruling()]
        assert_that(found, equal_to(expected))

    def test_no_review_on_a_draft_undrafted_with_the_plan_approved(self) -> None:
        """A review of the Execution only, the Plan carried over."""
        found = step_of(graded(*PLAN_APPROVED_ALONE, 1, sha=OLDER))
        assert_that(found, equal_to(flow.regular_review(Stage.EXECUTION_ONLY)))

    def test_no_review_is_a_review_of_both(self) -> None:
        """The first review grades the Plan and the Execution together."""
        assert_that(step_of(), equal_to(flow.regular_review(Stage.PLAN_AND_EXECUTION)))

    def test_an_approved_execution_with_a_conflict_is_the_workers(self) -> None:
        """No new review for a conflict-only fix."""
        found = step_of(graded(APPROVED, APPROVED, 1), mergeable_state="dirty")
        assert_that(found, equal_to(flow.worker(Task.RESOLVE_CONFLICT)))

    def test_a_review_without_a_plan_line_says_nothing_of_the_plan(self) -> None:
        """Its verdict is the execution's grade."""
        found = step_of(graded(None, None, 1))
        assert_that(found, equal_to(flow.merge()))

    def test_a_rejected_plan_after_an_unrelated_ruling_pauses(self) -> None:
        """The ruling is used whatever came before it."""
        found = step_of(ruling(1), graded(*PLAN_REJECTED, 2))
        assert_that(found, equal_to(flow.pause_for_owner()))


class TestRulings(unittest.TestCase):
    """What follows an Opus ruling."""

    def test_a_ruling_is_read_from_its_second_line(self) -> None:
        """``Ruling: <word>`` names it; anything else names none."""
        bodies = [
            "Opus ruling\nRuling: do these steps\n1. x",
            "Opus ruling\nRuling: revise the plan",
            "Opus ruling\nRuling: execution is approved",
            "Opus ruling\nRuling: split",
            "Opus ruling\nRuling: reshape",
            "Opus ruling\nRuling: abandon",
            "Opus ruling\nRuling: escalate to the owner",
            "Opus ruling\nRuling: whatever",
            "Opus ruling\nno ruling line",
            "Ruling: split",
        ]
        found = [flow.read_ruling(body) for body in bodies]
        ruled = flow.Ruling
        expected = [
            ruled.DO_THESE_STEPS,
            ruled.REVISE_THE_PLAN,
            ruled.EXECUTION_IS_APPROVED,
            ruled.SPLIT,
            ruled.RESHAPE,
            ruled.ABANDON,
            ruled.ESCALATE,
            None,
            None,
            None,
        ]
        assert_that(found, equal_to(expected))

    def test_do_these_steps_then_a_review_of_the_steps(self) -> None:
        """A worker does exactly the steps; a regular review checks only them."""
        found = flow.after_opus_ruling(state(), flow.Ruling.DO_THESE_STEPS)
        expected = (
            flow.worker(Task.RULING_STEPS),
            flow.regular_review(Stage.RULING_STEPS),
        )
        assert_that(found, equal_to(expected))

    def test_revise_the_plan_then_a_review_of_the_plan(self) -> None:
        """The plan only, then a review of the plan."""
        found = flow.after_opus_ruling(state(), flow.Ruling.REVISE_THE_PLAN)
        expected = (flow.worker(Task.REVISE_PLAN), flow.regular_review(Stage.PLAN_ONLY))
        assert_that(found, equal_to(expected))

    def test_an_approved_execution_merges_when_the_checks_are_green(self) -> None:
        """Otherwise the CI gate says what to do."""
        approved = flow.Ruling.EXECUTION_IS_APPROVED
        found = [
            flow.after_opus_ruling(state(checks=checks), approved)
            for checks in ((GREEN,), (RUNNING,), (RED,))
        ]
        expected = [
            (flow.merge(),),
            (flow.wait_for_ci(),),
            (flow.worker(Task.FIX_CI),),
        ]
        assert_that(found, equal_to(expected))

    def test_split_reshape_and_abandon_are_carried_out_as_ruled(self) -> None:
        """No check against the one-ticket-one-PR rules, whatever the PR is."""
        pulls_in_any_state = [
            state(),
            state(draft=True, body=""),
            state(graded(*PLAN_REJECTED, 1), ruling(2), checks=(RED,)),
        ]
        rulings = (flow.Ruling.SPLIT, flow.Ruling.RESHAPE, flow.Ruling.ABANDON)
        found = {
            flow.after_opus_ruling(each, ruled)
            for each in pulls_in_any_state
            for ruled in rulings
        }
        assert_that(found, equal_to({(flow.worker(Task.RULING_AS_GIVEN),)}))

    def test_escalating_pauses_for_the_owner(self) -> None:
        """The owner is told."""
        found = flow.after_opus_ruling(state(), flow.Ruling.ESCALATE)
        assert_that(found, equal_to((flow.pause_for_owner(),)))

    def test_every_step_says_what_to_do(self) -> None:
        """One line of text for each step, with its task or stage."""
        steps = [
            flow.worker(Task.REVISE_PLAN),
            flow.regular_review(Stage.PLAN_ONLY),
            flow.wait_for_owner(),
            flow.undraft(),
            flow.wait_for_undraft(),
            flow.wait_for_ci(),
            flow.opus_ruling(),
            flow.pause_for_owner(),
            flow.merge(),
        ]
        found = [flow.describe(each) for each in steps]
        assert_that([bool(text) and "\n" not in text for text in found], equal_to([True] * 9))
        assert_that(len(set(found)), equal_to(9))


class TestConfig(unittest.TestCase):
    """The flow reads the repository's own review form."""

    def test_the_paused_label_is_a_constant(self) -> None:
        """The label rules.md names."""
        assert_that(flow.PAUSED_LABEL, equal_to("paused-owner"))
        assert_that(isinstance(REVIEW, config.Review), equal_to(True))

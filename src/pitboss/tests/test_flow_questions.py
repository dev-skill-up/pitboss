"""Each question of the review flow alone, on recorded PR data (pitboss#107)."""

import unittest
from typing import Callable, Sequence

from hamcrest import assert_that, equal_to

from .. import flow, planbody, shapes
from . import test_flow

APPROVED = test_flow.APPROVED
CHANGES = test_flow.CHANGES
GREEN = test_flow.GREEN
OLDER = test_flow.OLDER
RED = test_flow.RED
RUNNING = test_flow.RUNNING
graded = test_flow.graded
state = test_flow.state

Case = tuple[flow.PullState, object]


def check(question: Callable[[flow.PullState], object], cases: Sequence[Case]) -> None:
    """Check the answers of a question.

    Args:
        question: the question.
        cases: each state and the answer it must give.
    """
    found = [question(pr) for pr, _ in cases]
    assert_that(found, equal_to([answer for _, answer in cases]))


def comment(body: str, second: int, author: str = "MEMBER") -> shapes.Comment:
    """An issue comment.

    Args:
        body: its text.
        second: the second of the minute it was written.
        author: its author's association.

    Returns:
        The comment.
    """
    when = f"2026-10-30T00:00:{second:02d}Z"
    return shapes.Comment(body=body, author_association=author, created_at=when)


class TestQuestions(unittest.TestCase):
    """The eleven questions."""

    def test_is_paused_for_owner(self) -> None:
        """The paused-owner label pauses a PR."""
        labelled = state(labels=frozenset({"paused-owner", "x"}))
        check(flow.is_paused_for_owner, [(labelled, True), (state(), False)])

    def test_has_plan_execution_body(self) -> None:
        """Both sections are needed, each as a heading of its own."""
        bodies = ["## Plan\nx\n## Execution\ny", "## Plan\nx\n", "Plan, Execution", ""]
        cases = [
            (state(body=each), want) for each, want in zip(bodies, [True] + [False] * 3)
        ]
        check(lambda each: planbody.has_plan_execution_body(each.pull.body), cases)

    def test_is_draft(self) -> None:
        """A draft is the PR's flag."""
        check(flow.is_draft, [(state(draft=True), True), (state(), False)])

    def test_can_undraft(self) -> None:
        """Undrafting is the runners' say, read by the caller."""
        clear = state(undraft_clear=True)
        check(flow.can_undraft, [(clear, True), (state(), False)])

    def test_has_conflict(self) -> None:
        """Only a dirty merge state is a conflict."""
        cases = [
            (state(mergeable_state=each), each == "dirty")
            for each in ("dirty", "clean", "behind")
        ]
        check(flow.has_conflict, cases)

    def test_ci_result(self) -> None:
        """Green, red, or none while it runs or has not started."""
        checks = [
            (GREEN,),
            (GREEN, RED),
            (RED, RUNNING),
            (GREEN, RUNNING),
            (),
            (RUNNING,),
        ]
        answers = [flow.Ci.GREEN, flow.Ci.RED, flow.Ci.RED, None, None, None]
        cases = [(state(checks=each), want) for each, want in zip(checks, answers)]
        check(flow.ci_result, cases)

    def test_plan_approved(self) -> None:
        """Some regular review graded the plan approved, at any head."""
        approving = graded(APPROVED, None, 1, sha=OLDER)
        rejecting = graded(CHANGES, None, 2)
        github = shapes.Graded(
            sha=OLDER, when="x", plan=APPROVED, execution=None, comment=False
        )
        cases = [
            (state(approving, rejecting), True),
            (state(rejecting), False),
            (state(graded(None, APPROVED, 1)), False),
            (state(github), False),
            (state(), False),
        ]
        check(flow.plan_approved, cases)

    def test_get_plan_rejections(self) -> None:
        """Each regular review that graded the plan changes needed counts."""
        rejecting = [graded(CHANGES, None, second) for second in (1, 2)]
        github = shapes.Graded(
            sha=OLDER, when="x", plan=CHANGES, execution=None, comment=False
        )
        cases = [
            (state(), 0),
            (state(rejecting[0]), 1),
            (state(*rejecting, graded(APPROVED, None, 3)), 2),
            (state(*rejecting, graded(None, CHANGES, 3)), 2),
            (state(rejecting[0], github), 1),
        ]
        check(flow.get_plan_rejections, cases)

    def test_opus_used(self) -> None:
        """A trusted comment whose first line is exactly ``Opus ruling``."""
        quoting = comment("I think the Opus ruling is", 2)
        cases = [
            (state(comments=[test_flow.ruling(1)]), True),
            (state(comments=[test_flow.ruling(1, author="NONE")]), False),
            (state(comments=[quoting]), False),
            (state(), False),
        ]
        check(flow.opus_used, cases)

    def test_execution_fixed_since_plan_approval(self) -> None:
        """An execution rejection on the approved plan at another head."""
        first = graded(APPROVED, CHANGES, 1, sha=OLDER)
        again = graded(None, CHANGES, 2)
        before = graded(CHANGES, CHANGES, 1, sha=OLDER)
        short = graded(APPROVED, CHANGES, 1, sha=state().pull.head.sha[:7])
        cases = [
            (state(graded(APPROVED, CHANGES, 1)), False),
            (state(first, again), True),
            (state(first), True),
            (state(before, again), False),
            (state(graded(CHANGES, None, 1)), False),
            (state(short, again), False),
            (state(), False),
            (test_flow.merged(state(first, again), OLDER), False),
            (test_flow.merged(state(first, again), "1" * 40), True),
        ]
        check(flow.execution_fixed_since_plan_approval, cases)

    def test_plan_rejected_again(self) -> None:
        """From the second rejection on; none and one are not again."""
        rejecting = [graded(CHANGES, None, second) for second in (1, 2, 3)]
        cases = [(state(*rejecting[:count]), count >= 2) for count in range(4)]
        check(flow.plan_rejected_again, cases)

    def test_newest_counting_review(self) -> None:
        """The newest regular review of the current head; GitHub's is none."""
        full = graded(APPROVED, CHANGES, 1)
        plain = graded(None, APPROVED, 2)
        older = graded(APPROVED, APPROVED, 3, sha=OLDER)
        github = shapes.Graded(
            sha=full.sha,
            when="2026-10-30T00:01:00Z",
            plan=None,
            execution=APPROVED,
            comment=False,
        )
        cases = [
            (state(full), full),
            (state(full, plain), plain),
            (state(full, older), full),
            (state(older), None),
            (state(), None),
            (state(full, github), full),
            (state(github), None),
        ]
        check(flow.newest_counting_review, cases)

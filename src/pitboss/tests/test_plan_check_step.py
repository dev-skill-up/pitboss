"""No Plan review is offered before a clean ``plan-check`` (pitboss#192)."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import flow, plancheck, plandigest, shapes, steps
from . import checkcomment, fakes, worldcomments
from .test_flow import CHANGES, expect, graded
from .test_flow import BODY
from .test_flow import state as checked_state

WITH_COMMANDS = "Fixes #7\n\n## Plan\nthe plan\n\n$ echo hi\n\n## Execution\nx\n"
EDITED = WITH_COMMANDS.replace("echo hi", "echo bye")
EMPTY_DIRECTIVE = "Fixes #7\n\n## Plan\nthe plan\n\n$ \n\n## Execution\nx\n"
QUOTED = "row 1: NOT RUN | Plan check: refused, rows that did not run: 1"
NO_COMMANDS = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nx\n"
PLAN_ALONE = steps.regular_review(steps.Stage.PLAN_ONLY)
BOTH = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)


def state(
    *recorded: shapes.Graded,
    body: str = BODY,
    draft: bool = False,
    comments: Sequence[shapes.Comment] = (),
) -> flow.PullState:
    """A PR with no recorded check but the ones the test gives.

    Args:
        *recorded: the reviews that count.
        body: its body.
        draft: whether it is a draft.
        comments: its issue comments.

    Returns:
        The state.
    """
    pr = checked_state(*recorded, body=body, draft=draft, comments=comments)
    return dataclasses.replace(pr, comments=pr.comments[:-1])


def check_comment(body: str, author: str = "MEMBER") -> shapes.Comment:
    """The comment of a clean ``plan-check`` of a body's Plan.

    Args:
        body: the PR body the check read.
        author: its author's association.

    Returns:
        The comment.
    """
    text = plancheck.text(plandigest.section(body), ["row 1: ran"], [])
    return shapes.Comment(
        body=text,
        author_association=author,
        created_at="2026-10-30T00:00:01Z",
        url="https://example.org/check/1",
    )


def refused_comment(body: str) -> shapes.Comment:
    """The comment of a ``plan-check`` that refused a body's Plan.

    Args:
        body: the PR body the check read.

    Returns:
        The comment.
    """
    text = plancheck.text(plandigest.section(body), ["row 1: NOT RUN"], [1])
    return dataclasses.replace(check_comment(body), body=text)


REFUSED = refused_comment(WITH_COMMANDS)
FIX = steps.worker(steps.Task.FIX_ROUND, REFUSED.url, QUOTED)
NOT_COUNTED = {
    "another plan": (EDITED, check_comment(WITH_COMMANDS)),
    "untrusted": (WITH_COMMANDS, check_comment(WITH_COMMANDS, author="NONE")),
    "not a check": (
        WITH_COMMANDS,
        dataclasses.replace(
            check_comment(WITH_COMMANDS), body="Fine\nPlan check: ok\n"
        ),
    ),
    "empty": (
        WITH_COMMANDS,
        dataclasses.replace(check_comment(WITH_COMMANDS), body=""),
    ),
}


class TestPlanCheckStep(unittest.TestCase):
    """No Plan review is offered for a Plan with commands before a clean check."""

    def test_a_clean_check_of_this_plan_offers_the_review(self) -> None:
        """A draft, a ready PR and a revised Plan wait, then are offered."""
        comments = [check_comment(WITH_COMMANDS)]
        rejected = graded(CHANGES, None, 1, sha=fakes.OLDER)
        cases = {
            "draft": (state(body=WITH_COMMANDS, draft=True), PLAN_ALONE),
            "ready": (state(body=WITH_COMMANDS), BOTH),
            "revised": (state(rejected, body=WITH_COMMANDS), PLAN_ALONE),
        }
        for name, (pr, review) in cases.items():
            with self.subTest(name):
                expect(steps.plan_check(), pr)
                expect(review, dataclasses.replace(pr, comments=comments))

    def test_a_check_that_does_not_count_leaves_the_step_a_check(self) -> None:
        """Another Plan's, a refusal, an untrusted author's, no check at all."""
        for name, (body, comment) in NOT_COUNTED.items():
            with self.subTest(name):
                shown = dataclasses.replace(state(body=body), comments=[comment])
                expect(steps.plan_check(), shown)

    def test_a_refusal_of_this_plan_is_the_fix_with_its_findings(self) -> None:
        """No review: the fix round quotes the findings (pitboss#390)."""
        expect(FIX, state(body=WITH_COMMANDS, draft=True, comments=[REFUSED]))
        expect(FIX, state(body=WITH_COMMANDS, draft=False, comments=[REFUSED]))
        assert_that(steps.describe(FIX), contains_string(QUOTED))

    def test_a_refusal_of_another_plan_is_a_check_to_run(self) -> None:
        """The edited Plan has no check of its own yet."""
        pr = state(body=EDITED, comments=[refused_comment(WITH_COMMANDS)])
        expect(steps.plan_check(), pr)

    def test_the_newest_check_of_this_plan_decides(self) -> None:
        """A clean check after a refusal gives the review; before it, the fix."""
        clean = check_comment(WITH_COMMANDS)
        later = dataclasses.replace(clean, created_at="2026-10-30T00:00:09Z")
        sooner = dataclasses.replace(clean, created_at="2026-10-30T00:00:00Z")
        pr = state(body=WITH_COMMANDS)
        expect(BOTH, dataclasses.replace(pr, comments=[REFUSED, later]))
        expect(FIX, dataclasses.replace(pr, comments=[REFUSED, sooner]))

    def test_a_directive_with_no_command_waits_for_the_check(self) -> None:
        """The check refuses it, so it is not offered for review."""
        expect(steps.plan_check(), state(body=EMPTY_DIRECTIVE, draft=True))

    def test_a_plan_without_commands_needs_the_check_too(self) -> None:
        """No comment, a check of an older digest, a check of the current one."""
        older = check_comment(NO_COMMANDS.replace("the plan", "the old plan"))
        current = check_comment(NO_COMMANDS)
        expect(steps.plan_check(), state(body=NO_COMMANDS, draft=True))
        expect(
            steps.plan_check(),
            state(body=NO_COMMANDS, draft=True, comments=[older]),
        )
        expect(PLAN_ALONE, state(body=NO_COMMANDS, draft=True, comments=[current]))

    def test_a_refused_plan_without_commands_is_the_fix(self) -> None:
        """The findings of the refusal are quoted, never a review."""
        found = "Done-when findings: the digest line is missing"
        text = plancheck.text(plandigest.section(NO_COMMANDS), [], [], [found])
        refused = dataclasses.replace(check_comment(NO_COMMANDS), body=text)
        pr = state(body=NO_COMMANDS, comments=[refused])
        assert_that(flow.next_step(pr).step, equal_to(steps.Step.WORKER))
        assert_that(steps.describe(flow.next_step(pr)), contains_string(found))

    def test_the_world_carries_the_clean_check_of_its_plan(self) -> None:
        """The literal of the fake GitHub is the check of the default body."""
        want = checkcomment.clean_text(fakes.PLAN_AND_EXECUTION)
        assert_that(worldcomments.CLEAN_CHECK["body"], equal_to(want))

    def test_the_step_says_what_to_do(self) -> None:
        """The line `next` prints."""
        assert_that(steps.describe(steps.plan_check()), contains_string("plan-check"))

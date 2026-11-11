"""A Plan approved after a ruling, a ruling just posted, an unwritten Execution.

pitboss#294: the sweep offered a fix-round review whose diff was ``git diff
85ec0de..85ec0de`` for a PR whose Plan was approved after an Opus ruling and
whose body was then filled in (bats-lang/zip#97 and bats-lang/quire#1060 are
its other two reproductions). Keywords: fix-round,
unwritten-execution.
"""

import dataclasses
import re
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import flow, planbody, shapes, steps
from . import fakes, test_flow, world
from .suggestions import kind_of_third, next_output, third
from .test_flow import APPROVED, CHANGES, GREEN, OLDER, graded, reading, state
from .test_flow_sweep import HEAD as WORLD_HEAD
from .test_flow_sweep import OLDER as WORLD_OLDER
from .test_flow_sweep import graded as comment
from .test_flow_sweep import reading as comment_reading
from .test_flow_sweep import world_with
from .test_plan_digest_collapse import digest

BODY = test_flow.BODY
EDITED = BODY + "\nEvidence added after the review.\n"
WORLD_EDITED = fakes.PLAN_AND_EXECUTION + "\nEvidence added after the review.\n"
EXECUTION = "## Execution\nthe work\n"
EDITED_PLAN = BODY.replace("the plan", "the plan, edited")
UNWRITTEN = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nNot started: later\n"
DIFF = re.compile(r"git diff (\w+)\.\.(\w+)")
PUSHED = dataclasses.replace(GREEN, started_at="2026-10-30T00:00:09Z")
REVIEW_EXECUTION = "review the Execution"
FIX_ROUND = "review the fix round's findings only"


def diffs(here: world.World) -> Sequence[tuple[str, str]]:
    """The two ends of each ``git diff`` a brief of ``slots next`` prints.

    Args:
        here: the world.

    Returns:
        The pairs.
    """
    return DIFF.findall(next_output(here))


def incident() -> world.World:
    """A rejected Plan, a ruling, an approved Plan, an edited body, green CI.

    Returns:
        The world.
    """
    rounds = [
        comment("changes needed", None, 1, sha=WORLD_OLDER),
        test_flow.ruling(2),
        comment_reading(comment("approved", None, 3), fakes.PLAN_AND_EXECUTION),
    ]
    return world_with(rounds, body=WORLD_EDITED)


def rejected_then_ruled() -> world.World:
    """An Execution rejection, the body edited after it, then the ruling.

    Returns:
        The world.
    """
    rounds = [
        comment_reading(
            comment("approved", "changes needed", 1), fakes.PLAN_AND_EXECUTION
        ),
        test_flow.ruling(2),
    ]
    return world_with(rounds, body=WORLD_EDITED)


def ruled_pr(checks: Sequence[shapes.CheckRun] = (GREEN,)) -> flow.PullState:
    """A PR whose Execution was rejected and a ruling followed, no review since.

    Args:
        checks: the check runs of its head.

    Returns:
        The state.
    """
    review = reading(graded(*test_flow.EXECUTION_REJECTED, 1), BODY)
    ruled = [test_flow.ruling(2)]
    return state(review, comments=ruled, checks=checks, body=EDITED)


def approved_alone(body: str, sha: str) -> flow.PullState:
    """A PR whose Plan was approved by a review of the Plan alone.

    Args:
        body: its body.
        sha: the head the review names.

    Returns:
        The state.
    """
    return state(graded(*test_flow.PLAN_APPROVED_ALONE, 1, sha=sha), body=body)


class TestApprovedPlanAfterARuling(unittest.TestCase):
    """Done-when 1 and 3: the review of the Execution, never a fix round."""

    def test_the_review_of_the_execution_is_next_and_no_fix_round(self) -> None:
        """Done-when 3: the header and the brief of PR 3 for the incident."""
        here = incident()
        header, brief = third(here)
        assert_that(header, contains_string(f": {REVIEW_EXECUTION}:"))
        assert_that("fix round" in "\n".join([header, *brief]).lower(), equal_to(False))
        assert_that(diffs(here), equal_to([]))

    def test_flow_gives_the_review_of_the_execution(self) -> None:
        """Done-when 1: no review counts, the Plan is approved: Execution only."""
        rounds = [
            graded(CHANGES, None, 1, sha=OLDER),
            reading(graded(APPROVED, None, 3), BODY),
        ]
        pr = state(*rounds, comments=[test_flow.ruling(2)], body=EDITED)
        test_flow.expect(steps.regular_review(steps.Stage.EXECUTION_ONLY), pr)


class TestNoFixRoundWithEqualHeads(unittest.TestCase):
    """Done-when 2: a fix round needs a review of changes needed and a new head."""

    def test_a_body_edited_at_the_head_is_not_a_fix_round(self) -> None:
        """Whatever the verdict, one head twice is no diff."""
        for verdict in ("changes needed", "approved"):
            with self.subTest(verdict):
                found = comment_reading(
                    comment("approved", verdict, 1), fakes.PLAN_AND_EXECUTION
                )
                here = world_with([found], body=WORLD_EDITED)
                assert_that(kind_of_third(here), equal_to(REVIEW_EXECUTION))
                assert_that(diffs(here), equal_to([]))

    def test_a_moved_head_is_a_fix_round_only_after_changes_needed(self) -> None:
        """Two different SHAs in the diff, or an approval and no fix round."""
        wants = {
            "changes needed": (FIX_ROUND, [(WORLD_OLDER, WORLD_HEAD)]),
            "approved": (REVIEW_EXECUTION, []),
        }
        for verdict, (kind, ends) in wants.items():
            with self.subTest(verdict):
                found = comment("approved", verdict, 1, sha=WORLD_OLDER)
                here = world_with([found])
                assert_that(kind_of_third(here), equal_to(kind))
                assert_that(diffs(here), equal_to(ends))


class TestRulingJustPosted(unittest.TestCase):
    """The step after a ruling nobody applied is the ruling's, not a review."""

    def test_the_worker_applies_the_ruling(self) -> None:
        """zip#97: not a review, the worker round of ``do these steps``."""
        here = rejected_then_ruled()
        assert_that(kind_of_third(here), equal_to("do the steps of the Opus ruling"))

    def test_flow_gives_the_ruling_steps(self) -> None:
        """No review counts and none followed the ruling."""
        test_flow.expect(test_flow.ruling_steps(2), ruled_pr())

    def test_a_push_after_the_ruling_hands_the_pr_to_the_review(self) -> None:
        """A check run of the head that started after the ruling: applied."""
        pr = ruled_pr(checks=[PUSHED])
        test_flow.expect(steps.regular_review(steps.Stage.EXECUTION_ONLY), pr)

    def test_the_ruling_of_a_plan_revision_is_the_workers(self) -> None:
        """``revise the plan`` before any review of this head."""
        ruled = test_flow.ruling(2, line="Ruling: revise the plan")
        rejected = graded(*test_flow.EXECUTION_REJECTED, 1, sha=OLDER)
        test_flow.expect(
            steps.worker(steps.Task.REVISE_PLAN), state(rejected, comments=[ruled])
        )

    def test_a_review_after_the_ruling_ends_it(self) -> None:
        """The review is newer than the ruling: the flow reads the review."""
        newer = graded(*test_flow.EXECUTION_REJECTED, 3, sha=OLDER)
        want = steps.regular_review(steps.Stage.EXECUTION_ONLY)
        test_flow.expect(want, state(newer, comments=[test_flow.ruling(2)]))


def pointed(run: int) -> str:
    """A body whose Plan has a CI pointer that names a run and its job.

    Args:
        run: the run's id (the job's is the next).

    Returns:
        The body.
    """
    row = f"https://github.com/o/r/actions/runs/{run}/job/{run + 1}"
    return f"## Plan\n1. CI: workflow `check.yml`, job `check`: {row}\n\n{EXECUTION}"


def read(body: str, sha: str = test_flow.HEAD) -> shapes.Graded:
    """An Execution rejection that records the digest of the Plan of a body.

    Args:
        body: the body it read.
        sha: the head it reviewed.

    Returns:
        The review.
    """
    review = graded(*test_flow.EXECUTION_REJECTED, 1, sha=sha)
    return dataclasses.replace(review, plan_digest=digest(body))


def ruled(
    body: str, read_body: str, checks: Sequence[shapes.CheckRun], sha: str
) -> flow.PullState:
    """A PR whose review read one Plan, whose body now has another, and a ruling.

    Args:
        body: its body now.
        read_body: the body the review read.
        checks: the check runs of its head.
        sha: the head the review named.

    Returns:
        The state.
    """
    comments = [test_flow.ruling(2)]
    return state(read(read_body, sha), comments=comments, checks=checks, body=body)


class TestRulingOfAnEditedPlan(unittest.TestCase):
    """pitboss#475: a ruling is executed after the Plan changed."""

    def test_the_ruling_due_is_offered_at_plan_edited(self) -> None:
        """Done-when 2: edited Plan, no revision, no review or push after."""
        pr = ruled(EDITED_PLAN, BODY, [GREEN], test_flow.HEAD)
        test_flow.expect(steps.worker(steps.Task.RULING_STEPS), pr)

    def test_a_push_after_the_ruling_leaves_the_hold(self) -> None:
        """The nearest input: the ruling is applied, the Plan stays edited."""
        pr = ruled(EDITED_PLAN, BODY, [PUSHED], test_flow.HEAD)
        test_flow.expect(steps.plan_edited(), pr)

    def test_the_fix_round_with_new_urls_is_re_reviewed(self) -> None:
        """Done-when 4: ruling, new head, URL-only change, green checks."""
        pr = ruled(pointed(7), pointed(1), [PUSHED], OLDER)
        found = flow.next_step(pr)
        assert_that(found, equal_to(steps.regular_review(steps.Stage.EXECUTION_ONLY)))


class TestUnwrittenExecution(unittest.TestCase):
    """quire#1060: an approved Plan with a placeholder Execution is a worker's."""

    def test_the_sweep_offers_the_worker_round_not_a_review(self) -> None:
        """The Plan was approved alone and the Execution says not started."""
        here = world_with([comment("approved", None, 1)], body=UNWRITTEN)
        assert_that(
            kind_of_third(here),
            equal_to("run the Plan's commands and fill the Execution"),
        )

    def test_flow_with_the_plan_approved_at_an_older_or_this_head(self) -> None:
        """The review of this head or of an older one grades the Plan alone."""
        for sha in (OLDER, test_flow.HEAD):
            with self.subTest(sha):
                pr = approved_alone(UNWRITTEN, sha)
                test_flow.expect(steps.worker(steps.Task.RUN_PLAN), pr)

    def test_a_written_execution_is_reviewed(self) -> None:
        """The nearest input that is not a placeholder."""
        pr = approved_alone(BODY, test_flow.HEAD)
        test_flow.expect(steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN), pr)


def unwritten(text: str) -> bool:
    """Whether a body with the text under its Execution heading is unwritten.

    Args:
        text: what the Execution section holds.

    Returns:
        The answer of ``planbody``.
    """
    return planbody.execution_unwritten(
        f"## Plan\nx\n\n## Execution\n{text}\n\n## Evidence\nrow\n"
    )


class TestExecutionUnwritten(unittest.TestCase):
    """What ``planbody.execution_unwritten`` calls a placeholder."""

    def test_placeholders(self) -> None:
        """Empty, and first lines that say it is not done."""
        for text in (
            "",
            "\n\n",
            "Not started: it is written after the Plan is approved",
            "not yet written",
            "- Not started",
            "_TBD_",
            "TODO",
            "To be written",
            "Written after the review",
        ):
            with self.subTest(text):
                assert_that(unwritten(text), equal_to(True))

    def test_written_text(self) -> None:
        """Text that does not start as a placeholder."""
        for text in (
            "Ran the commands; all passed.",
            "Notes: not started nothing",
            "\nStarted at once, not started late.",
            "Todos were all done.",
        ):
            with self.subTest(text):
                assert_that(unwritten(text), equal_to(False))

    def test_other_bodies(self) -> None:
        """No Execution section, and a placeholder in a later section."""
        bodies = [
            "## Plan\nonly a plan, Not started\n",
            "",
            "## Execution\nDone.\n\n## Evidence\nNot started\n",
        ]
        wants = [planbody.execution_unwritten(each) for each in bodies]
        assert_that(wants, equal_to([False, False, False]))

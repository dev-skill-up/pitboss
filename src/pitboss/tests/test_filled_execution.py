"""A filled Execution under a clean Plan check is reviewed, not run again (pitboss#390).

The Plan was approved alone after an Opus ruling (keyword: filled-execution);
the worker round that runs the Plan's commands and fills the Execution is only
for an Execution that is empty or a placeholder, or a Plan no clean check covers.
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import flow, plancheckflow, shapes, steps
from . import test_flow
from .test_flow import APPROVED, CHANGES, OLDER, expect, graded, state, with_no_drafts
from .checkcomment import clean_check
from .test_plan_check_step import WITH_COMMANDS, check_comment, refused_comment

UNWRITTEN = "Fixes #7\n\n## Plan\nthe plan\n\n## Execution\nNot started: later\n"
DONE = UNWRITTEN.replace("Not started: later", "done")
RUN = steps.worker(steps.Task.RUN_PLAN)
REVIEW = steps.regular_review(steps.Stage.EXECUTION_AGAINST_PLAN)
RULED = [test_flow.ruling(3)]


def alone(body: str, comments: Sequence[shapes.Comment]) -> flow.PullState:
    """A PR whose Plan was approved alone after two rejections and a ruling.

    Args:
        body: its body.
        comments: its comments besides the ruling.

    Returns:
        The state.
    """
    rejected = (graded(CHANGES, None, 1, sha=OLDER), graded(CHANGES, None, 2))
    approved = graded(APPROVED, None, 4)
    pr = state(*rejected, approved, body=body)
    return dataclasses.replace(pr, comments=[*RULED, *comments])


class TestFilledExecution(unittest.TestCase):
    """The Execution rows are filled, and the Plan check matches."""

    def test_a_filled_execution_is_reviewed_and_an_unwritten_one_is_run(self) -> None:
        """The placeholder is the worker's, a Plan with no command needs a check."""
        expect(REVIEW, alone(test_flow.BODY, [clean_check(test_flow.BODY)]))
        expect(RUN, alone(test_flow.BODY, []))
        expect(RUN, alone(UNWRITTEN, []))

    def test_a_plan_with_commands_needs_its_clean_check(self) -> None:
        """No check, a refusal and another Plan's check leave the worker round."""
        filled = WITH_COMMANDS
        expect(REVIEW, alone(filled, [check_comment(filled)]))
        expect(RUN, alone(filled, []))
        expect(RUN, alone(filled, [refused_comment(filled)]))
        edited = filled.replace("echo hi", "echo bye")
        expect(RUN, alone(edited, [check_comment(filled)]))

    def test_the_question_alone(self) -> None:
        """Written and checked, or not."""
        trusted = frozenset({"MEMBER"})
        clean = check_comment(WITH_COMMANDS)
        cases = [
            (WITH_COMMANDS, [clean], True),
            (WITH_COMMANDS, [], False),
            (UNWRITTEN, [], False),
            (DONE, [check_comment(DONE)], True),
            (DONE, [], False),
        ]
        for body, comments, want in cases:
            with self.subTest(body):
                found = plancheckflow.filled(body, comments, trusted)
                assert_that(found, equal_to(want))

    def test_a_repository_with_no_drafts_writes_the_body_instead(self) -> None:
        """It never prints `run the Plan's commands` (keyword: no-drafts)."""
        quiet = with_no_drafts(alone(UNWRITTEN, []))
        expect(steps.worker(steps.Task.FIRST_ROUND), quiet)
        checked = [clean_check(test_flow.BODY)]
        filled = with_no_drafts(alone(test_flow.BODY, checked))
        expect(REVIEW, filled)

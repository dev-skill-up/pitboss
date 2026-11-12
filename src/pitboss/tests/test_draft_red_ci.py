"""A draft whose own head turned the CI red gets a fix round (keyword: draft-red-ci).

``slots next`` offered a review for such a draft (pitboss#464, quire#1104).
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import draftfacts, flow, shapes, steps
from . import fakes, suggestions, world
from .test_flow import RED, expect, state

LOG = "Failed check log: test: https://github.com/owner/project/runs/8"
RUNNING = {"id": 9, "name": "test", "status": "in_progress", "conclusion": None}


def draft_world(checks: Sequence[object]) -> world.World:
    """A world whose PR 3 is a draft with these checks on its head.

    Args:
        checks: the check runs of PR 3's head.

    Returns:
        The world.
    """
    here = world.make_world()
    here.bodies.update(world.pull_bodies("owner/project", 3, checks, "clean"))
    head = {"sha": "3" * 40, "ref": "branch-3"}
    here.bodies["repos/owner/project/pulls/3"] = fakes.pull_body(
        3, draft=True, head=head, mergeable_state="clean"
    )
    return here


def failing(name: str) -> shapes.CheckRun:
    """A completed failed check run.

    Args:
        name: its name.

    Returns:
        The run.
    """
    return shapes.CheckRun(id=len(name), name=name, finished=True, failed=True)


def set_check(name: str) -> flow.PullState:
    """A draft whose only check, named ``test``, failed, with a Plan review check.

    Args:
        name: the check the Plan review waits for.

    Returns:
        The state.
    """
    found = state(checks=(RED,), draft=True)
    draft = dataclasses.replace(found.draft, plan_review_check=name)
    return dataclasses.replace(found, draft=draft)


class TestDraftRedCi(unittest.TestCase):
    """The step of a draft with a failed check."""

    def test_t464_the_step_is_a_fix(self) -> None:
        """A failed check on a draft's head is fixed, not reviewed."""
        expect(steps.worker(steps.Task.FIX_CI), state(checks=(RED,), draft=True))

    def test_t464_the_offered_step_names_the_check_and_its_job(self) -> None:
        """The suggestion is a fix of the CI with the failed check's log."""
        header, lines = suggestions.third(draft_world([world.RED]))
        assert_that(header, contains_string("fix the CI"))
        assert_that(LOG in lines, equal_to(True))

    def test_t464_the_brief_is_a_fix_on_the_branch_with_the_check(self) -> None:
        """Its PITBOSS-SLOT line ends in fix and the brief holds the check."""
        output = suggestions.next_output(draft_world([world.RED]))
        slot = "PITBOSS-SLOT: owner/project#3 fix"
        assert_that(slot in output.splitlines(), equal_to(True))
        assert_that(output, contains_string("test: https://github.com"))

    def test_t464_a_running_check_keeps_the_review(self) -> None:
        """A draft whose check still runs is not fixed."""
        header = suggestions.third(draft_world([RUNNING]))[0]
        assert_that(header, contains_string("review"))

    def test_t464_green_checks_keep_the_review(self) -> None:
        """A draft whose checks are green is not fixed."""
        header = suggestions.third(draft_world([world.GREEN]))[0]
        assert_that(header, contains_string("review"))

    def test_a_failed_plan_review_check_alone_keeps_the_review(self) -> None:
        """The check the Plan review waits for failing is the review's own case."""
        expect(steps.regular_review(steps.Stage.PLAN_ONLY), set_check("test"))

    def test_another_failed_check_is_fixed_beside_the_plan_review_check(self) -> None:
        """A failure of a check with another name is a fix, whatever is set."""
        expect(steps.worker(steps.Task.FIX_CI), set_check("plan"))

    def test_a_job_of_a_called_workflow_is_the_named_check(self) -> None:
        """``caller / name`` is the check of that name; a name ending alike is not."""
        called = [failing("x / plan")]
        other = [failing("x / explan")]
        assert_that(draftfacts.failed_besides(called, "plan"), equal_to(False))
        assert_that(draftfacts.failed_besides(other, "plan"), equal_to(True))

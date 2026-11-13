"""A repository with no drafts gets one combined review once CI is green (pitboss#390).

Pitboss opens its PRs ready and one review covers the Plan and the Execution
(keyword: no-drafts; the owner, 2026-11-08T06:30Z): the sweep never prints
`review the Plan alone` or `run the Plan's commands` for such a repository,
prints the combined review once CI is green at the head, and `waiting for CI at
this head` before.
"""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import flow, steps
from ..markers import Marker
from . import fakes, quietworld, test_flow, world
from . import test_flow_sweep as sweeps
from .suggestions import kind_of_third, next_output
from .test_flow import GREEN, OLDER, RUNNING, expect, state, with_no_drafts

COMBINED = "review the Plan and the Execution"
ALONE = "review the Plan alone"
WAITING = "waiting for CI at this head"
LISTED = '[slots.brief]\nno_drafts = ["owner/project"]\n\n[runners]'
REVISED = test_flow.graded(test_flow.CHANGES, None, 1, sha=OLDER)


def revised() -> world.World:
    """A world whose PR 3 had its Plan rejected and revised.

    Returns:
        The world.
    """
    return sweeps.world_with([sweeps.graded(sweeps.CHANGES, None, 1, sha=OLDER)])


def listed() -> world.World:
    """The same world, with its repository in ``[slots.brief] no_drafts``.

    Returns:
        The world.
    """
    here = revised()
    quietworld.edit_config(here, "[runners]", LISTED)
    return here


def state_line(here: world.World) -> str:
    """PR 3's ``PR STATE`` line.

    Args:
        here: the world.

    Returns:
        The line.
    """
    shown = next_output(here).splitlines()
    return "".join(
        x for x in shown if x.startswith(Marker.PR_STATE.text) and "#3:" in x
    )


class TestFlow(unittest.TestCase):
    """The step, with the repository's drafts off."""

    def test_a_revised_plan_is_reviewed_with_the_execution(self) -> None:
        """Where drafts exist it is graded alone; here the one review covers both."""
        expect(steps.regular_review(steps.Stage.PLAN_ONLY), state(REVISED))
        pr = with_no_drafts(state(REVISED))
        expect(steps.regular_review(steps.Stage.PLAN_AND_EXECUTION), pr)

    def test_ci_that_has_not_finished_is_waited_for(self) -> None:
        """Before green, nobody reviews."""
        prs = [
            state(REVISED, checks=each) for each in ((), (RUNNING,), (GREEN, RUNNING))
        ]
        found = [flow.next_step(with_no_drafts(each)) for each in prs]
        assert_that(found, equal_to([steps.ci_pending()] * 3))

    def test_a_draft_is_marked_ready_never_reviewed_alone(self) -> None:
        """The undraft when the runners allow it, else the wait for the window."""
        draft = with_no_drafts(state(draft=True, checks=()))
        expect(steps.UNDRAFT_PENDING, draft)
        expect(steps.undraft(), dataclasses.replace(draft, undraft_clear=True))


class TestSweep(unittest.TestCase):
    """A ready PR of a listed repository, green and pending."""

    def test_green_ci_gives_the_combined_review(self) -> None:
        """Never the Plan alone, after a rejected Plan was revised."""
        assert_that(kind_of_third(revised()), equal_to("review the Plan alone"))
        here = listed()
        assert_that(kind_of_third(here), equal_to(COMBINED))
        assert_that(ALONE in next_output(here), equal_to(False))

    def test_drafts_off_for_the_project_gives_the_same_review(self) -> None:
        """``[slots.brief] drafts = false`` names no repository, and covers all."""
        here = revised()
        quiet = "[slots.brief]\ndrafts = false\n\n[runners]"
        quietworld.edit_config(here, "[runners]", quiet)
        assert_that(kind_of_third(here), equal_to(COMBINED))

    def test_pending_ci_waits(self) -> None:
        """The same PR with no check run at its head."""
        here = listed()
        runs = fakes.page(f"{world.PROJECT}/commits/{sweeps.HEAD}/check-runs")
        here.bodies[runs] = {"check_runs": []}
        assert_that(state_line(here), contains_string(WAITING))
        assert_that(COMBINED in next_output(here), equal_to(False))

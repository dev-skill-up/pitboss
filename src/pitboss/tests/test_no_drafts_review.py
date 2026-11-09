"""A repository with no drafts gets one combined review once CI is green (pitboss#390).

Keyword: no-drafts. Pitboss opens its PRs ready and one review covers the Plan
and the Execution (the owner, 2026-11-08T06:30Z): the sweep never prints `review
the Plan alone` or `run the Plan's commands` for such a repository, prints the
combined review once CI is green at the head, and `waiting for CI at this head`
before.
"""

import dataclasses
import unittest

from hamcrest import assert_that, contains_string, equal_to

from .. import config, flow, steps
from ..markers import Marker
from . import fakes, quietworld, world
from . import test_flow_sweep as flows
from .suggestions import kind_of_third, next_output
from .test_flow import CHANGES, GREEN, OLDER, RUNNING, expect, graded, state

COMBINED = "review the Plan and the Execution"
ALONE = "review the Plan alone"
WAITING = "waiting for CI at this head"
LISTED = '[slots.brief]\nno_drafts = ["owner/project"]\n\n[runners]'
REVISED = graded(CHANGES, None, 1, sha=OLDER)


def pitboss_like(pr: flow.PullState) -> flow.PullState:
    """A PR of a repository whose PRs open ready.

    Args:
        pr: the PR.

    Returns:
        The same with that recorded.
    """
    return dataclasses.replace(pr, no_drafts=True)


def listed(here: world.World) -> None:
    """Put the world's repository in ``[slots.brief] no_drafts``.

    Args:
        here: the world.
    """
    quietworld.edit_config(here, "[runners]", LISTED)


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
        both = steps.regular_review(steps.Stage.PLAN_AND_EXECUTION)
        alone = steps.regular_review(steps.Stage.PLAN_ONLY)
        expect(alone, state(REVISED))
        expect(both, pitboss_like(state(REVISED)))

    def test_ci_that_has_not_finished_is_waited_for(self) -> None:
        """Before green, nobody reviews."""
        for checks in ((), (RUNNING,), (GREEN, RUNNING)):
            expect(steps.wait_for_ci(), pitboss_like(state(REVISED, checks=checks)))

    def test_a_draft_is_marked_ready_never_reviewed_alone(self) -> None:
        """The undraft when the runners allow it, else the wait for the window."""
        draft = pitboss_like(state(draft=True, checks=()))
        expect(steps.wait_for_undraft(), draft)
        expect(steps.undraft(), dataclasses.replace(draft, undraft_clear=True))


class TestSettings(unittest.TestCase):
    """Which repositories open ready."""

    def test_the_list_and_the_setting_decide(self) -> None:
        """A listed repository, or any when drafts are off."""
        listed_only = config.Project(
            repo=config.make_repo("o", "r"),
            base_branch="main",
            main_clone=fakes.directory(),
            workspace=fakes.directory(),
            no_drafts=frozenset({"o/r"}),
        )
        off = dataclasses.replace(listed_only, no_drafts=frozenset(), drafts=False)
        assert_that(
            [each.opens_ready("o/r") for each in (listed_only, off)],
            equal_to([True] * 2),
        )
        assert_that(listed_only.opens_ready("o/other"), equal_to(False))
        assert_that(off.opens_ready("o/other"), equal_to(True))


class TestSweep(unittest.TestCase):
    """A ready PR of a listed repository, green and pending."""

    def test_green_ci_gives_the_combined_review(self) -> None:
        """Never the Plan alone, after a rejected Plan was revised."""
        control = flows.world_with([flows.graded(flows.CHANGES, None, 1, sha=OLDER)])
        assert_that(kind_of_third(control), equal_to("review the Plan alone"))
        here = flows.world_with([flows.graded(flows.CHANGES, None, 1, sha=OLDER)])
        listed(here)
        assert_that(kind_of_third(here), equal_to(COMBINED))
        assert_that(ALONE in next_output(here), equal_to(False))

    def test_drafts_off_for_the_project_gives_the_same_review(self) -> None:
        """``[slots.brief] drafts = false`` names no repository, and covers all."""
        here = flows.world_with([flows.graded(flows.CHANGES, None, 1, sha=OLDER)])
        quietworld.edit_config(
            here, "[runners]", "[slots.brief]\ndrafts = false\n\n[runners]"
        )
        assert_that(kind_of_third(here), equal_to(COMBINED))

    def test_pending_ci_waits(self) -> None:
        """The same PR with no check run at its head."""
        here = flows.world_with([flows.graded(flows.CHANGES, None, 1, sha=OLDER)])
        listed(here)
        runs = fakes.page(f"{world.PROJECT}/commits/{flows.HEAD}/check-runs")
        here.bodies[runs] = {"check_runs": []}
        assert_that(state_line(here), contains_string(WAITING))
        assert_that(COMBINED in next_output(here), equal_to(False))

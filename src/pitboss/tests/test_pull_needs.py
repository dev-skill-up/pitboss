"""A red PR or one behind the base says what it needs (keyword: pull-needs, #415)."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import basefix, config, headchecks, pulls, reviews, shapes, updateline
from . import fakes, test_flow, test_work, world
from .test_commands import sweep
from .test_flow_sweep import TWO_PLAN_REJECTIONS, world_with
from .test_slot_commands import next_output

QUEUE = "\n[merge_queue]\nrepositories = ['project']\n"
DISPATCH = " ".join(
    [
        "re-dispatch owner/project's relock.yml (workflow_dispatch),",
        "never a re-run of the failed job",
    ]
)
BEHIND = "merge main into branch-3, check, push"
PASSED = dataclasses.replace(test_flow.GREEN, id=3, name="test")
ANSWERED = headchecks.HeadSignals(
    fixed=[basefix.Answer(failed=test_flow.RED, passed=PASSED)]
)
OPEN = headchecks.HeadSignals()
GREEN = test_work.GREEN
RED = test_flow.RED
RED_NEED = "the CI is red: fix it (merge main first if it is behind)"
CASES = [
    # name, state, relock, checks, signals, extra TOML, need, whether the sweep says it
    (
        "relock red and answered",
        "clean",
        True,
        (RED,),
        ANSWERED,
        "",
        f"the red check passed on main since: {DISPATCH}",
        True,
    ),
    ("ordinary red and answered", "clean", False, (RED,), ANSWERED, "", RED_NEED, True),
    ("relock red, not answered", "clean", True, (RED,), OPEN, "", RED_NEED, True),
    ("relock conflicting", "dirty", True, (RED,), ANSWERED, "", RED_NEED, True),
    ("ordinary behind", "behind", False, (GREEN,), OPEN, "", BEHIND, False),
    (
        "relock behind",
        "behind",
        True,
        (GREEN,),
        OPEN,
        "",
        f"{BEHIND}, then {DISPATCH}",
        True,
    ),
    ("behind in a merge queue", "behind", False, (GREEN,), OPEN, QUEUE, "", False),
    ("clean and green", "clean", False, (GREEN,), OPEN, "", "", False),
]


def settings_of(extra: str) -> config.Config:
    """The configuration of a world whose PR 3 is behind, with more TOML.

    Args:
        extra: more TOML, appended.

    Returns:
        The configuration.
    """
    here = world.make_world()
    lines = [extra, world.EXTRA.replace("{ledger}", str(here.ledger))]
    return fakes.settings(extra="\n".join(lines), directory=here.workspace)


def pull_in(
    state: str,
    relock: bool,
    checks: Sequence[shapes.CheckRun],
    signals: headchecks.HeadSignals,
) -> pulls.PullFacts:
    """A PR of the project in a state, with check runs and signals.

    Args:
        state: its ``mergeable_state``.
        relock: whether its branch is a relock branch.
        checks: the check runs of its head.
        signals: what else may block it.

    Returns:
        The PR.
    """
    base = test_work.facts(3, reviews.Standing.NONE, **{"mergeable_state": state})
    return dataclasses.replace(base, signals=signals, relock=relock, checks=checks)


class TestNeeds(unittest.TestCase):
    """The need of each state, with the nearest states that must differ."""

    def test_each_state_says_what_it_needs(self) -> None:
        """Relock and ordinary PRs; red, answered, behind, queued, clean."""
        for name, state, relock, checks, signals, extra, need, line in CASES:
            with self.subTest(name):
                pull = pull_in(state, relock, checks, signals)
                settings = settings_of(extra)
                said = updateline.need_lines(pull, settings)
                assert_that(
                    (updateline.needs(pull, settings), bool(said)),
                    equal_to((need, line)),
                )

    def test_only_a_relock_pr_is_told_to_dispatch(self) -> None:
        """The same answered red check on an ordinary branch has no dispatch."""
        settings = settings_of("")
        found = [
            "re-dispatch"
            in updateline.needs(pull_in("clean", relock, (RED,), ANSWERED), settings)
            for relock in (True, False)
        ]
        assert_that(found, equal_to([True, False]))


class TestListed(unittest.TestCase):
    """The need reaches ``slots next`` and the sweep."""

    def test_the_list_and_the_sweep_say_what_a_red_pr_needs(self) -> None:
        """A NEXT line ends with the need; the sweep has a NEEDS line."""
        here = world_with(TWO_PLAN_REJECTIONS, mergeable_state="behind")
        listed = next_output(here)
        swept = sweep(here).out
        assert_that(
            [
                "PR 1; needs: the CI is red: fix it" in listed,
                "NEEDS owner/project#1: " in swept,
            ],
            equal_to([True, True]),
        )

"""Tests for the UPDATE kind: a PR behind the base with its checks finished."""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to

from .. import pulls, reviews, shapes, steps, updateline
from . import fakes, test_work, world
from .test_commands import sweep
from .test_slot_commands import next_output

DONE = test_work.GREEN
RUNNING = dataclasses.replace(DONE, finished=False)
QUEUE = "\n[merge_queue]\nrepositories = ['project']\n"
UPDATE_LINE = (
    "UPDATE owner/project#3: merge main into branch-3, check, push"
    " (never rewrite history)"
)


def facts(state: str, checks: Sequence[shapes.CheckRun]) -> pulls.PullFacts:
    """An open PR of the project with a merge state and check runs.

    Args:
        state: its ``mergeable_state``.
        checks: its head's check runs.

    Returns:
        The PR.
    """
    done = bool(checks) and all(each.finished for each in checks)
    green = test_work.facts(3, reviews.Standing.NONE, mergeable_state=state)
    step = test_work.DEFAULT_STEP if done else steps.wait_for_ci()
    return dataclasses.replace(green, checks=checks, step=step)


def behind_world(extra: str = "") -> world.World:
    """A world whose PR 3 is behind the base, its checks finished.

    Args:
        extra: more TOML appended to the configuration.

    Returns:
        The world.
    """
    here = world.make_world()
    key = "repos/owner/project/pulls/3"
    details = dict(fakes.pull_body(3), mergeable_state="behind")
    details["head"] = {"sha": "3" * 40, "ref": "branch-3"}
    here.bodies[key] = details
    fakes.settings(here.workspace, world.EXTRA.format(ledger=here.ledger) + extra)
    return here


CASES = [
    ("behind", (DONE,), "", [UPDATE_LINE]),
    ("behind", (DONE, RUNNING), "", []),
    ("behind", (), "", []),
    ("clean", (DONE,), "", []),
    ("behind", (DONE,), QUEUE, []),
    ("behind", (DONE,), "\n[merge_queue]\nrepositories = ['other']\n", [UPDATE_LINE]),
]


class TestSweepAndNext(unittest.TestCase):
    """``pitboss sweep`` and ``pitboss slots next``."""

    def test_sweep_lists_it_and_next_lists_the_step(self) -> None:
        """The sweep names the update; ``slots next`` lists what the step says."""
        here = behind_world()
        found = (
            UPDATE_LINE in sweep(here).out.splitlines(),
            "(update" in next_output(here),
        )
        assert_that(found, equal_to((True, False)))

    def test_a_merge_queue_repository_lists_no_update(self) -> None:
        """Configured as merge-queue, nothing is named update."""
        here = behind_world(QUEUE)
        found = ("UPDATE " in sweep(here).out, "(update" in next_output(here))
        assert_that(found, equal_to((False, False)))


class TestLine(unittest.TestCase):
    """The sweep line alone."""

    def test_line_only_for_an_update(self) -> None:
        """A PR gets the line exactly when it is behind with its checks finished."""
        lines = [
            updateline.lines(
                facts(state, checks), fakes.settings(fakes.directory(), extra)
            )
            for state, checks, extra, _ in CASES
        ]
        assert_that(lines, equal_to([expected for *_, expected in CASES]))

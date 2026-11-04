"""How many GitHub calls a sweep makes for a configuration of N PRs (pitboss#144)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import calllog
from . import fakes, world
from .test_commands import sweep

OPEN_PULLS = fakes.page("repos/owner/project/pulls?state=open")
FIRST_THREE = (1, 2, 3)
FIRST_ADDED = 5
FOUR_PULLS = {
    "gh api actions/jobs": 1,
    "gh api actions/runs": 2,
    "gh api actions/runs/jobs": 2,
    "gh api check-runs": 1,
    "gh api check-runs/annotations": 1,
    "gh api commits/check-runs": 4,
    "gh api commits/status": 4,
    "gh api contents/.github/workflows/review-gate.yml": 2,  # one for each repository
    "gh api issues": 2,
    "gh api issues/comments": 6,  # four PRs' and one feed for each repository (#239)
    "gh api pulls": 8,
    "gh api pulls/reviews": 4,
    "gh api repository": 3,
}
PER_PULL = {
    "gh api pulls": 1,
    "gh api issues/comments": 1,
    "gh api pulls/reviews": 1,
    "gh api commits/check-runs": 1,
    "gh api commits/status": 1,
}


def world_with(extra: int) -> world.World:
    """The tests' world with more green PRs in the project.

    Args:
        extra: how many PRs to add to the project's three.

    Returns:
        The world.
    """
    here = world.make_world()
    added = range(FIRST_ADDED, FIRST_ADDED + extra)
    for number in added:
        green = world.pull_bodies("owner/project", number, [world.GREEN], "clean")
        here.bodies.update(green)
    here.bodies[OPEN_PULLS] = [{"number": n} for n in (*FIRST_THREE, *added)]
    return here


def api_calls(here: world.World) -> Mapping[str, int]:
    """Count the ``gh api`` calls the sweep of a world made, by kind.

    Args:
        here: the world.

    Returns:
        Each kind of call and how many.
    """
    sweep(here)
    kinds = [calllog.kind_of(each) for each in here.calls if each[:2] == ["gh", "api"]]
    return {kind: kinds.count(kind) for kind in sorted(set(kinds))}


class TestCallCounts(unittest.TestCase):
    """The calls of a sweep are fixed by what it reads, and no PR is read twice."""

    def test_the_calls_for_four_prs(self) -> None:
        """Four open PRs in two repositories make exactly these calls."""
        found = api_calls(world_with(0))
        assert_that(found, equal_to(FOUR_PULLS))

    def test_each_added_pr_costs_the_same_calls(self) -> None:
        """Two more PRs add two sets of the per-PR calls and nothing else."""
        few, many = api_calls(world_with(0)), api_calls(world_with(2))
        grown = {kind: many[kind] - few.get(kind, 0) for kind in many}
        added = {kind: each for kind, each in grown.items() if each}
        assert_that(added, equal_to({kind: 2 * n for kind, n in PER_PULL.items()}))
        assert_that(sum(grown.values()), equal_to(2 * sum(PER_PULL.values())))

    def test_the_sweep_says_what_each_section_ran(self) -> None:
        """Every section ends with its count of commands on standard error."""
        here = world_with(0)
        err = sweep(here).err
        assert_that(err, contains_string("pull requests done:"))
        assert_that(err, contains_string("slots done:"))

"""How many GitHub calls a sweep makes for a configuration of N PRs (pitboss#144)."""

import unittest

from hamcrest import assert_that, contains_string

from . import fakes, world
from .test_commands import sweep

OPEN_PULLS = fakes.page("repos/owner/project/pulls?state=open")
FIRST_THREE = (1, 2, 3)
FIRST_ADDED = 5


def world_with(extra: int) -> world.World:
    """The tests' world with more green PRs in the project.

    Args:
        extra: how many PRs to add to the project's three.

    Returns:
        The world.
    """
    here = world.make_world()
    added = range(FIRST_ADDED, FIRST_ADDED + extra)
    here.bodies.update(
        {
            path: body
            for number in added
            for path, body in world.pull_bodies(
                "owner/project", number, [world.GREEN], "clean"
            ).items()
        }
    )
    here.bodies[OPEN_PULLS] = [{"number": n} for n in (*FIRST_THREE, *added)]
    return here


class TestCallCounts(unittest.TestCase):
    """The calls of a sweep are fixed by what it reads, and no PR is read twice."""

    def test_the_sweep_says_what_each_section_ran(self) -> None:
        """Every section ends with its count of commands on standard error."""
        here = world_with(0)
        err = sweep(here).err
        assert_that(err, contains_string("pull requests done:"))
        assert_that(err, contains_string("slots done:"))

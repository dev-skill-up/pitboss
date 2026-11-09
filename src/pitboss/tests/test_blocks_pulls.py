"""A blocker with an open PR is named with it, ranked with the oldest waiting (#388).

quire#573 was a tracking ticket; three of its four blockers had open PRs
(pitboss#383/392, #94/387, #369/393), the shape a test with no PR does not have.
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from . import fakes, rankworld, world
from .rankworld import lines_are, lines_of, next_output, printed, starts, sweep
from .test_closing_comment import BLOCKED_BY_FOUR, tracking_world

LIBRARY = world.LIBRARY
NINTH = "owner/project#9"
RANK = f"blocks {NINTH}; ranked urgent, opened 2026-09-01"
PULLS = {392: 383, 387: 94, 393: 369}
CLOSING = "Status. It closes when owner/lib#94 and owner/lib#369 have merged."


def pulled(here: world.World, fixed: Mapping[int, int]) -> None:
    """Open PRs of the library, each of which fixes a ticket of it.

    Args:
        here: the world.
        fixed: each PR's number and the ticket it fixes.
    """
    listing = fakes.page(f"{LIBRARY}/pulls?state=open")
    opened = here.bodies[listing]
    assert isinstance(opened, list)
    here.bodies[listing] = [*opened, *({"number": n} for n in fixed)]
    for number, ticket in fixed.items():
        here.bodies.update(
            world.pull_bodies("owner/lib", number, [world.GREEN], "clean")
        )
        here.bodies[fakes.page(f"{LIBRARY}/issues/{number}/comments")] = []
        found = here.bodies[f"{LIBRARY}/pulls/{number}"]
        assert isinstance(found, dict)
        found["body"] = f"Fixes #{ticket}\n\n{found['body']}"


class TestTrackingTicket(unittest.TestCase):
    """quire#573 with its four blockers, three of them under open PRs."""

    def test_the_four_blockers_with_their_pull_requests(self) -> None:
        """BLOCKED names the tickets; BLOCKS names them, the PR after three."""
        here = tracking_world()
        pulled(here, PULLS)
        output = next_output(here)
        lines_are(output, "BLOCKED", [BLOCKED_BY_FOUR])
        blocks = [
            f"BLOCKS owner/lib#383 (PR owner/lib#392): {RANK}",
            f"BLOCKS owner/lib#94 (PR owner/lib#387): {RANK}",
            f"BLOCKS owner/lib#369 (PR owner/lib#393): {RANK}",
            f"BLOCKS owner/lib#384: {RANK}",
        ]
        lines_are(output, "BLOCKS", blocks)

    def test_the_steps_and_the_start_stand_in_the_blockers_place(self) -> None:
        """The three PRs' steps and the start of #384 come before ticket 10."""
        here = tracking_world()
        pulled(here, PULLS)
        ahead = ["owner/lib#392", "owner/lib#387", "owner/lib#393", "owner/lib#384"]
        assert_that(
            starts(here),
            equal_to(
                ["owner/project#1", "owner/project#3", *ahead, "owner/project#10"]
            ),
        )

    def test_the_sweep_prints_the_same(self) -> None:
        """The sweep has the BLOCKED line, the BLOCKS lines and no start for #9."""
        here = tracking_world()
        pulled(here, PULLS)
        out = sweep(here).out
        lines_are(out, "BLOCKED", [BLOCKED_BY_FOUR])
        assert_that(len(lines_of(out, "BLOCKS")), equal_to(4))
        rankworld.absent(out, "start a PR: owner/project#9")


class TestClosesWhen(unittest.TestCase):
    """The same ticket, whose newest comment says it closes when two PRs merge."""

    def test_two_blockers_under_open_pull_requests(self) -> None:
        """BLOCKED names the two tickets, and the ticket has no start line."""
        here = tracking_world(CLOSING)
        pulled(here, {387: 94, 393: 369})
        blocked = "BLOCKED owner/project#9 by owner/lib#94, owner/lib#369"
        printed(here, "BLOCKED", [blocked])
        assert_that(NINTH in starts(here), equal_to(False))
        blocks = [
            f"BLOCKS owner/lib#94 (PR owner/lib#387): {RANK}",
            f"BLOCKS owner/lib#369 (PR owner/lib#393): {RANK}",
        ]
        printed(here, "BLOCKS", blocks)

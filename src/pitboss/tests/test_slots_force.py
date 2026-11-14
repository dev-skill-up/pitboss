"""D5, D6 and D11: a correction and the quiesce.

``case post`` records a correction against its ticket and ``quiesce on`` starts no
ticket until ``off`` (keyword: quiesce); pitboss#444, items 10.
"""

import unittest

from hamcrest import assert_that, equal_to

from .. import quiesce
from . import refused, world
from .cleanworld import same
from .itemworld import one, with_pull_issues
from .says import says
from .rankworld import mentioning
from .test_case_post import BODY, CASE, case_world, post, started
from .fastvariants import named
from .fastworld import NINTH, fast_world, listed

STARTS = "WORKER: owner/project#9: write the code"


class TestCorrection(unittest.TestCase):
    """D5 and D6: a correction is recorded against its ticket, in its body."""

    def test_d5_d6_a_correction_is_added_to_the_ticket_body(self) -> None:
        """The case follows the body; no comment is made."""
        here = case_world([])
        done = post(here, CASE)
        same(done.code, 0)
        same(refused.bodies(here), [BODY + "\n" + CASE])
        same(any("comments" in call[-1] for call in here.calls), False)

    def test_d5_d6_a_correction_to_a_started_ticket_is_refused(self) -> None:
        """The nearest input it must still refuse: a PR already fixes the ticket."""
        here = case_world(started())
        refused.assert_refused(post(here, CASE), "PR #4 says it fixes", here)
        same(refused.bodies(here), [])


def switch(here: world.World, state: str) -> world.Result:
    """Run ``quiesce on`` or ``off``.

    Args:
        here: the world.
        state: ``on`` or ``off``.

    Returns:
        What it did.
    """
    return world.invoke(here, "quiesce", state, "--config", here.config)


class TestQuiesce(unittest.TestCase):
    """D11: no ticket starts until the owner lifts the quiesce."""

    def test_d11_slots_next_offers_nothing_while_quiesced(self) -> None:
        """No decision starts ticket 9; off, and it is offered again."""
        here = world.make_world()
        on = switch(here, "on")
        same((on.code, on.out), (0, quiesce.LINE + "\n"))
        quiet = listed(here)
        same(quiet.code, 0)
        same(mentioning(quiet.out, STARTS), [])
        off = switch(here, "off")
        says(off.out, "quiesce is off")
        assert_that(len(mentioning(listed(here).out, STARTS)) > 0, equal_to(True))
        switch(here, "off")

    def test_d11_the_brief_of_one_item_is_refused_while_quiesced(self) -> None:
        """Ticket 9 has no decision while quiesced; off, it is briefed."""
        here = with_pull_issues(fast_world())
        switch(here, "on")
        same(mentioning(one(here, NINTH).out, STARTS), [])
        switch(here, "off")
        done = one(here, NINTH)
        same(done.code, 0)
        says(done.out, STARTS)


class TestForce(unittest.TestCase):
    """``--force`` decides a ticket an open PR keeps by its own record."""

    def test_force_briefs_a_ticket_that_a_pr_keeps(self) -> None:
        """Plain, the PR keeps ticket 9 and nothing starts it; forced, it is briefed."""
        here = with_pull_issues(named())
        plain, forced = (one(here, NINTH, *more) for more in ((), ("--force",)))
        same(
            (plain.code, forced.code, STARTS in plain.out, STARTS in forced.out),
            (1, 0, False, True),
        )

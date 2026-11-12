"""D1 to D11: what an UNKNOWN says, ``--force``, a correction and the quiesce.

``slots next ITEM`` says the rule and the data that decided an UNKNOWN (keyword:
unknown-data), ``--force`` prints the brief the plain command refuses (keyword:
force-brief), ``case post`` records a correction against its ticket and ``quiesce
on`` offers nothing until ``off`` (keyword: quiesce); pitboss#444, items 10.
"""

import unittest

from hamcrest import assert_that, equal_to

from .. import quiesce
from . import refused, world
from .cleanworld import same
from .itemworld import one, with_pull_issues
from .says import lacks, says
from .rankworld import NEXT_LINE, dependent_world, mentioning
from .test_case_post import BODY, CASE, case_world, post, started
from .fastvariants import closed, named, superseded, waiting
from .fastworld import NINTH, SLOT, fast_world, listed


def both(
    here: world.World, reference: str, *more: str
) -> tuple[world.Result, world.Result]:
    """Run ``slots next ITEM`` plain, then with ``--force``.

    Args:
        here: the world.
        reference: the item.
        *more: more arguments for both.

    Returns:
        What the plain command did, and what the forced one did.
    """
    return one(here, reference, *more), one(here, reference, *more, "--force")


def silent(done: world.Result) -> None:
    """Require a refusal: status 1 and nothing on standard output.

    Args:
        done: what a command did.
    """
    same((done.code, done.out), (1, ""))


class TestUnknownData(unittest.TestCase):
    """D1: an UNKNOWN says the rule and the data that decided it."""

    def test_d1_the_pr_that_names_the_ticket_is_in_the_reason(self) -> None:
        """The PR's number, and the rule: title, body or branch."""
        found = one(with_pull_issues(named()), NINTH)
        silent(found)
        says(
            found.err,
            "an open PR already works on it: PR owner/project#4 names it in its",
            "title, body or branch",
        )

    def test_d1_a_hold_and_a_blocker_say_their_data(self) -> None:
        """The blocker's reference, the superseding, the hold."""
        for build, why in (
            (waiting, "it waits for owner/lib#3"),
            (superseded, "it is superseded"),
        ):
            with self.subTest(why):
                says(one(with_pull_issues(build()), NINTH).err, why)


class TestForce(unittest.TestCase):
    """D2 and D3: ``--force`` prints the brief the plain command refuses."""

    def test_d2_d3_force_prints_the_brief_and_says_what_it_overrode(self) -> None:
        """The brief on standard output, the refusal on standard error."""
        here = with_pull_issues(named())
        before = here.ledger.read_text()
        plain, done = both(here, NINTH)
        silent(plain)
        same(done.code, 0)
        assert_that(len(done.out) > 0, equal_to(True))
        says(
            done.err,
            "FORCED: the plain command refuses: UNKNOWN: owner/project#9",
            "PR owner/project#4 names it",
        )
        same(here.ledger.read_text(), before)

    def test_d2_d3_force_overrides_a_blocker_a_supersession_and_a_blocked_pr(
        self,
    ) -> None:
        """A ticket that waits, a superseded one, and a PR whose ticket waits."""
        for build, reference in (
            (waiting, NINTH),
            (superseded, NINTH),
            (dependent_world, "owner/project#3"),
        ):
            with self.subTest(build.__name__):
                here = with_pull_issues(build())
                plain, done = both(here, reference)
                same(plain.code, 1)
                same(done.code, 0)
                says(done.err, "FORCED: the plain command refuses")

    def test_d2_d3_force_does_not_open_a_closed_ticket(self) -> None:
        """The nearest input it must still refuse: nothing to brief."""
        done = one(with_pull_issues(closed()), NINTH, "--force")
        silent(done)
        says(done.err, "it is closed or cannot be read")
        lacks(done.err, "FORCED")

    def test_d2_d3_force_prices_a_ticket_with_no_label_at_zero(self) -> None:
        """A slot works on an unlabeled ticket: forced, its brief is printed."""
        here = with_pull_issues(world.make_world())
        ticket = "owner/project#50"
        held = ("set", SLOT, "agent-1", "#50", "--running", "agent-1")
        world.invoke(here, "slots", held[0], here.config, *held[1:])
        plain, done = both(here, ticket, "--running", "agent-1")
        same(plain.code, 1)
        same(done.code, 0)
        says(
            done.err, "FORCED: the plain command refuses", "a slot already works on it"
        )


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
    """D11: nothing starts until the owner lifts the quiesce."""

    def test_d11_slots_next_offers_nothing_while_quiesced(self) -> None:
        """No NEXT, no brief, no empty slot; off, and the list is back."""
        here = world.make_world()
        on = switch(here, "on")
        same((on.code, on.out), (0, quiesce.LINE + "\n"))
        quiet = listed(here)
        same(quiet.code, 0)
        says(quiet.out, quiesce.LINE)
        found = (
            len(NEXT_LINE.findall(quiet.out)),
            len(mentioning(quiet.out, "EMPTY SLOT")),
            len(mentioning(quiet.out, "DISPATCH")),
        )
        same(found, (0, 0, 0))
        off = switch(here, "off")
        says(off.out, "quiesce is off")
        back = listed(here)
        assert_that(len(NEXT_LINE.findall(back.out)) > 0, equal_to(True))
        lacks(back.out, "QUIESCED")
        switch(here, "off")

    def test_d11_the_brief_of_one_item_is_refused_while_quiesced(self) -> None:
        """UNKNOWN with the quiesce line; control: off, it is briefed."""
        here = with_pull_issues(fast_world())
        switch(here, "on")
        done = one(here, NINTH)
        same((done.code, done.out), (1, ""))
        says(done.err, "UNKNOWN: owner/project#9 is not offered: QUIESCED")
        switch(here, "off")
        same(one(here, NINTH).code, 0)

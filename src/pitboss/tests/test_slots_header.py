"""The first lines of ``slots next`` and ``LEDGER STALE`` (pitboss#415)."""

import re
import unittest

from hamcrest import assert_that, equal_to

from . import suggestions, world
from .test_handback import slots, start
from .test_owner_repositories import lines_of as printed

FREE = (
    "FREE SLOT: {n} of 2 free since 2030-01-01 00:00Z; dispatch before reading"
    " anything else"
)


def second_next(output: str) -> str:
    """The second NEXT line of an output (the first is the running agents').

    Args:
        output: what ``slots next`` printed.

    Returns:
        The line.
    """
    return printed(output, "NEXT 2.")[0]


def unconfirmed(here: world.World) -> str:
    """What ``slots next`` prints with no ``--running``.

    Args:
        here: the world.

    Returns:
        Its output.
    """
    after = ("--now", world.FUTURE)
    return world.invoke(here, "slots", "next", "--config", here.config, *after).out


class TestHeader(unittest.TestCase):
    """The running agents by kind, the count against the cap, the free slot."""

    def test_one_worker_under_a_cap_of_two_frees_a_slot(self) -> None:
        """The count, the worker, FREE SLOT with its time, and START."""
        here = world.make_world()
        start(here)
        out = suggestions.next_output(here)
        assert_that(
            out.splitlines()[:3],
            equal_to(
                [
                    "SLOTS 1 of 2, free: big",
                    "RUNNING worker owner/project#9",
                    FREE.format(n=1),
                ]
            ),
        )
        assert_that(printed(out, "START"), equal_to(["START " + second_next(out)]))

    def test_two_running_agents_free_nothing(self) -> None:
        """No FREE SLOT and no START under a full cap."""
        here = world.make_world()
        start(here)
        slots(here, "set", "big", "agent-2", "#3", "--running", "agent-1", "agent-2")
        out = suggestions.next_output(here)
        assert_that(out.splitlines()[0], equal_to("SLOTS 2 of 2, free: none"))
        assert_that(printed(out, "FREE SLOT"), equal_to([]))
        assert_that(printed(out, "START"), equal_to([]))

    def test_each_kind_is_listed_by_kind(self) -> None:
        """A reviewer and a fix round are named by their PR."""
        cases = [
            ("review", "tiny", "#3", "RUNNING reviewer owner/project#3"),
            ("fix", "big", "#3", "RUNNING fix round owner/project#3"),
        ]
        for kind, slot, pull, said in cases:
            with self.subTest(kind):
                here = world.make_world()
                words = ("set", slot, "agent-1", pull, "--kind", kind)
                slots(here, *words, "--running", "agent-1")
                found = printed(suggestions.next_output(here), "RUNNING")
                assert_that(found, equal_to([said]))

    def test_the_ledger_is_stale_only_with_rows_and_no_running_list(self) -> None:
        """Rows nobody confirmed are said first; an empty ledger has none."""
        here = world.make_world()
        empty = unconfirmed(here)
        start(here)
        full = unconfirmed(here)
        assert_that(printed(empty, "LEDGER STALE"), equal_to([]))
        first, second = full.splitlines()[:2]
        stale = re.fullmatch(r"LEDGER STALE: last written [\d-]+ [\d:]+Z, (.*)", first)
        assert_that(
            (stale.group(1) if stale else None, second),
            equal_to(
                ("1 rows name agents nobody has confirmed", "SLOTS 1 of 2, free: big")
            ),
        )

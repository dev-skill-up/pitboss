"""The first lines of ``slots next`` and ``LEDGER STALE`` (pitboss#415)."""

import unittest

from hamcrest import assert_that, equal_to, starts_with

from . import suggestions, world
from .test_handback import slots, start
from .test_owner_repositories import lines_of

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
    return lines_of(output, "NEXT 2.")[0]


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
        assert_that(lines_of(out, "START"), equal_to(["START " + second_next(out)]))

    def test_two_running_agents_free_nothing(self) -> None:
        """No FREE SLOT and no START under a full cap."""
        here = world.make_world()
        start(here)
        slots(here, "set", "big", "agent-2", "#3", "--running", "agent-1", "agent-2")
        out = suggestions.next_output(here)
        assert_that(out.splitlines()[0], equal_to("SLOTS 2 of 2, free: none"))
        assert_that(lines_of(out, "FREE SLOT"), equal_to([]))
        assert_that(lines_of(out, "START"), equal_to([]))

    def test_each_kind_is_listed_by_kind(self) -> None:
        """A reviewer and a fix round are named by their PR."""
        here = world.make_world()
        slots(
            here,
            "set",
            "tiny",
            "agent-1",
            "#3",
            "--kind",
            "review",
            "--running",
            "agent-1",
        )
        slots(
            here,
            "set",
            "big",
            "agent-2",
            "#2",
            "--kind",
            "fix",
            "--running",
            "agent-1",
            "agent-2",
        )
        out = suggestions.next_output(here)
        assert_that(
            lines_of(out, "RUNNING"),
            equal_to(
                [
                    "RUNNING reviewer owner/project#3",
                    "RUNNING fix round owner/project#2",
                ]
            ),
        )

    def test_no_running_list_says_the_ledger_is_stale(self) -> None:
        """Rows nobody confirmed are said first."""
        here = world.make_world()
        start(here)
        out = world.invoke(
            here, "slots", "next", here.config, "--now", world.FUTURE
        ).out
        first, second = out.splitlines()[:2]
        assert_that(first, starts_with("LEDGER STALE: last written "))
        assert_that(
            first.endswith("1 rows name agents nobody has confirmed"), equal_to(True)
        )
        assert_that(second, equal_to("SLOTS 1 of 2, free: big"))

    def test_an_empty_ledger_is_not_stale(self) -> None:
        """No row, nothing to confirm."""
        here = world.make_world()
        out = world.invoke(
            here, "slots", "next", here.config, "--now", world.FUTURE
        ).out
        assert_that(lines_of(out, "LEDGER STALE"), equal_to([]))

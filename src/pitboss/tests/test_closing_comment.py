"""A tracking ticket whose newest comment says it closes when others merge (#388).

The cause: quire#573 was offered as "start a PR" twice, and a worker handed back
NOT STARTED, because its last status comment said it closed when pitboss#94 and
pitboss#369 had merged.
"""

import unittest
from typing import Sequence

from hamcrest import assert_that, contains_string, equal_to

from .. import ticketblock
from . import rankworld, world
from .rankworld import lines_are, next_output, printed, starts, sweep

REPOSITORY = rankworld.REPOSITORY
STATUS = (
    "Status. What is not shipped is tracked here: owner/lib#383, owner/lib#384,"
    " owner/lib#94 and owner/lib#369. This ticket is superseded by them; it closes"
    " when #383, #384, #94 and #369 have merged."
)
FOUR = ["owner/lib#383", "owner/lib#384", "owner/lib#94", "owner/lib#369"]
BLOCKED_BY_FOUR = "BLOCKED owner/project#9 by " + ", ".join(FOUR)


def tracking_world(
    text: str = STATUS, open_ones: Sequence[int] = (383, 384, 94, 369)
) -> world.World:
    """Ticket 9 is a tracking ticket; the library has the tickets it waits for.

    Args:
        text: the newest comment of ticket 9.
        open_ones: the numbers of the library's tickets that are open.

    Returns:
        The world.
    """
    here = rankworld.blocked_world(
        "Keep the sweep as a skill.", comments=[rankworld.comment(text)]
    )
    for number in (383, 384, 94, 369):
        state = "open" if number in open_ones else "closed"
        found = rankworld.ticket(
            "", state, number, created_at="2026-09-09T00:00:00Z", labels=[]
        )
        rankworld.serve(here, "owner/lib", number, found)
    return here


class TestClosing(unittest.TestCase):
    """The sentence of the status comment."""

    def test_the_status_comment_of_the_cause(self) -> None:
        """The four tickets, the bare numbers in the repository the comment names."""
        found = ticketblock.closing(STATUS, REPOSITORY)
        assert_that(list(found), equal_to(FOUR))

    def test_the_forms(self) -> None:
        """Another verb form, a bare number of the ticket's own repository."""
        closing = ticketblock.closing
        cases = {
            "It closes when #4 merges": ["owner/project#4"],
            "closes  when\nowner/lib#5 and lib#6 has been merged": [
                "owner/lib#5",
                "owner/lib#6",
            ],
            "closes when #7 is merged": ["owner/project#7"],
            "closes when owner/lib#8 and #9 merge (see owner/lib#9)": [
                "owner/lib#8",
                "owner/lib#9",
            ],
            "it closes when the work is done": [],
            "does not close when #4 is mentioned": [],
            "closes when #4 is open": [],
            "closes when #1 is done. Then owner/lib#5 merged.": [],
        }
        for text, expected in cases.items():
            with self.subTest(text):
                assert_that(list(closing(text, REPOSITORY)), equal_to(expected))

    def test_only_the_newest_text_counts(self) -> None:
        """An older status comment is replaced by the newer one."""
        blockers = ticketblock.open_blockers
        old = "closes when #3 has merged"
        new = "Closing: the work moved."
        for texts, expected in [
            (["body", old], ["owner/project#3"]),
            (["body", old, new], []),
            ([old], []),
        ]:
            with self.subTest(texts):
                found = blockers(REPOSITORY, texts, lambda reference: True)
                assert_that(list(found), equal_to(expected))

    def test_a_blocker_that_is_closed_or_one_s_own_blocks_nothing(self) -> None:
        """Only an open ticket blocks, and never the ticket itself."""
        blockers = ticketblock.open_blockers
        texts = ["Depends on #3 and depends on #4. Depends on #3"]
        found = blockers(REPOSITORY, texts, lambda reference: reference.endswith("#4"))
        assert_that(list(found), equal_to(["owner/project#4"]))
        mine = blockers(REPOSITORY, texts, lambda reference: True, {"owner/project#3"})
        assert_that(list(mine), equal_to(["owner/project#4"]))


class TestSlotsNext(unittest.TestCase):
    """The line and the offer of ``slots next`` for the tracking ticket."""

    def test_the_line_names_every_open_blocker(self) -> None:
        """BLOCKED lists them, there is no start line, and each blocker is offered."""
        here = tracking_world()
        output = next_output(here)
        lines_are(output, "BLOCKED", [BLOCKED_BY_FOUR])
        assert_that(
            starts(here),
            equal_to(["owner/project#1", "owner/project#3", *FOUR, "owner/project#10"]),
        )
        blocks = [
            f"BLOCKS {each}: blocks owner/project#9; ranked urgent, opened 2026-09-01"
            for each in FOUR
        ]
        lines_are(output, "BLOCKS", blocks)

    def test_a_blocker_that_has_merged_is_left_out(self) -> None:
        """Two of the four are closed: the line names the two that are open."""
        here = tracking_world(open_ones=(94, 369))
        expected = "BLOCKED owner/project#9 by owner/lib#94, owner/lib#369"
        printed(here, "BLOCKED", [expected])

    def test_every_blocker_has_merged(self) -> None:
        """The ticket is offered again, in its own place."""
        here = tracking_world(open_ones=())
        printed(here, "BLOCKED", [])
        assert_that(
            starts(here),
            equal_to(
                [
                    "owner/project#1",
                    "owner/project#3",
                    "owner/project#9",
                    "owner/project#10",
                ]
            ),
        )

    def test_a_comment_that_is_not_the_newest_does_not_count(self) -> None:
        """A newer comment that does not say it replaces the status."""
        here = tracking_world()
        newer = rankworld.comment("The status above is out of date.")
        here.bodies[rankworld.COMMENTS] = [
            rankworld.comment(STATUS),
            newer,
        ]
        printed(here, "BLOCKED", [])

    def test_the_sweep_prints_the_same(self) -> None:
        """The sweep has the BLOCKED line and no start for the ticket."""
        out = sweep(tracking_world()).out
        lines_are(out, "BLOCKED", [BLOCKED_BY_FOUR])
        assert_that(out, contains_string("SLOTS FREE 1: 7 queued"))

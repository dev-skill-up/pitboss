"""A ticket that many others name as their cause is ranked as p0 (pitboss#388).

Owner, 2026-11-08 15:08Z: "From now on, if a ticket causes this many issues, it's
a p0".
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import config, promotion
from . import fakes, quietworld, rankworld, world
from .rankworld import (
    lines_are,
    mentioning,
    next_output,
    printed,
    publish,
    starts,
    sweep,
)

PROJECT = world.PROJECT
NINTH = "owner/project#9"
RANKS = ["p0", "p1", "p2", "p3"]
TICKETS = {9: "p3", 10: "p1", 11: "p2", 12: "p2"}
SAID = (
    "PROMOTE owner/project#9 to p0: caused 3 corrections"
    " (owner/project#10, owner/project#11, owner/project#12)"
)
REPOSITORY = config.make_repo("owner", "project")


def named_world(
    bodies: Mapping[int, str],
    owner: Mapping[str, str] | None = None,
    ranks: Mapping[int, str] = TICKETS,
    states: Mapping[int, str] | None = None,
) -> world.World:
    """Open tickets 9 to 12 with these priority labels and bodies.

    The listing of every ticket and PR of the project (``issues?state=all``) holds
    these tickets, in the state each has.

    Args:
        bodies: each ticket's number and its body.
        owner: the owner's stated priorities.
        ranks: each ticket's number and its priority label.
        states: each ticket's state, ``open`` when it is not here.

    Returns:
        The world.
    """
    here = world.make_world()
    quietworld.edit_config(here, '["urgent"]', str(RANKS).replace("'", '"'))
    table = "".join(f'"{each}" = "{at}"\n' for each, at in (owner or {}).items())
    quietworld.edit_config(here, "[slots]", f"[slots.owner_priorities]\n{table}[slots]")
    shown = {
        number: (rank, (states or {}).get(number, "open"))
        for number, rank in ranks.items()
    }
    publish(here, RANKS, shown)
    for number, body in bodies.items():
        found = here.bodies[f"{PROJECT}/issues/{number}"]
        assert isinstance(found, dict)
        found["body"] = body
    every = [here.bodies[f"{PROJECT}/issues/{number}"] for number in ranks]
    here.bodies[fakes.page(f"{PROJECT}/issues?state=all")] = every
    return here


THREE = {
    10: "Caused by #9\nCaused by #11",
    11: "Cause: #9",
    12: "Caused by owner/project#9",
}


class TestCaused(unittest.TestCase):
    """The mentions that count."""

    def test_the_forms(self) -> None:
        """``Caused by`` with or without a colon and ``Cause:``, in any case."""
        cases = {
            "Caused by #5": ["owner/project#5"],
            "caused by: owner/lib#6": ["owner/lib#6"],
            "CAUSE: lib#7 and Cause: #8": ["owner/lib#7", "owner/project#8"],
            "Cause #10": [],
            "because #11": [],
            "caused by the sweep": [],
        }
        for text, expected in cases.items():
            with self.subTest(text):
                assert_that(
                    list(promotion.caused(text, REPOSITORY)), equal_to(expected)
                )

    def test_each_ticket_or_pull_request_counts_once(self) -> None:
        """A second mention in the same text and a mention of itself do not count."""
        found = promotion.tally(
            [
                ("owner/project#1", "Caused by #5, caused by #5 and Cause: #1"),
                ("owner/lib#2", "Caused by owner/project#5"),
            ]
        )
        assert_that(
            dict(found),
            equal_to({"owner/project#5": ["owner/project#1", "owner/lib#2"]}),
        )

    def test_a_ticket_with_the_top_priority_has_no_line(self) -> None:
        """Only a ticket below the top, named twice or more, is promoted."""
        sources = [
            ("a/b#1", "Caused by owner/project#5"),
            ("a/b#2", "Cause: owner/project#5"),
            ("a/b#3", "Caused by owner/project#6"),
        ]
        found = promotion.named_by(
            ["owner/project#5", "owner/project#6"], sources, {"owner/project#5"}
        )
        assert_that(dict(found), equal_to({}))
        found = promotion.named_by(
            ["owner/project#5", "owner/project#6"], sources, set()
        )
        assert_that(
            {k: list(v) for k, v in found.items()},
            equal_to({"owner/project#5": ["a/b#1", "a/b#2"]}),
        )


class TestSlotsNext(unittest.TestCase):
    """The ranking and the line of ``slots next``."""

    def test_a_ticket_named_by_three_is_ranked_p0(self) -> None:
        """Ticket 9 (p3) comes first with its own age; ticket 11 (named once) stays."""
        here = named_world(THREE)
        later = ["owner/project#10", "owner/project#11"]
        first = ["owner/project#1", "owner/project#3", NINTH]
        assert_that(starts(here), equal_to([*first, *later]))
        output = next_output(here)
        lines_are(output, "PROMOTE", [SAID])
        assert_that(
            output, contains_string(f"{NINTH} (start a PR p0, opened 2026-09-01,")
        )
        assert_that(
            output,
            contains_string("owner/project#11 (start a PR p2, opened 2026-09-03,"),
        )

    def test_without_the_mentions_the_order_is_by_label(self) -> None:
        """The same tickets with no cause named: ticket 9 is last, p3."""
        here = named_world({})
        rankworld.without_project_pulls(here)
        assert_that(
            starts(here),
            equal_to(
                ["owner/project#10", "owner/project#11", "owner/project#12", NINTH]
            ),
        )
        printed(here, "PROMOTE", [])

    def test_named_by_two_is_more_than_once(self) -> None:
        """Two tickets name ticket 9: it is promoted, with K = 2."""
        here = named_world({10: "Caused by #9", 11: "Cause: #9"})
        said = (
            "PROMOTE owner/project#9 to p0: caused 2 corrections"
            " (owner/project#10, owner/project#11)"
        )
        printed(here, "PROMOTE", [said])

    def test_named_once_keeps_its_label(self) -> None:
        """One ticket names ticket 9: no line, and it stays last."""
        here = named_world({10: "Caused by #9"})
        rankworld.without_project_pulls(here)
        printed(here, "PROMOTE", [])
        assert_that(starts(here)[-1], equal_to(NINTH))

    def test_a_ticket_that_names_itself_is_not_promoted(self) -> None:
        """Its own text, said twice, is not another ticket."""
        here = named_world({9: "Caused by #9. Cause: #9", 10: "Cause: #9"})
        printed(here, "PROMOTE", [])

    def test_the_owner_states_the_priority(self) -> None:
        """The owner's p3 for ticket 9 stays, whatever names it."""
        here = named_world(THREE, {NINTH: "p3"})
        rankworld.without_project_pulls(here)
        printed(here, "PROMOTE", [])
        assert_that(starts(here)[-1], equal_to(NINTH))

    def test_a_ticket_that_is_p0_has_no_line(self) -> None:
        """Ticket 9 already has the top label."""
        here = named_world(THREE, ranks={**TICKETS, 9: "p0"})
        printed(here, "PROMOTE", [])


class TestSweep(unittest.TestCase):
    """The sweep prints the line once."""

    def test_the_line_is_printed_once(self) -> None:
        """One PROMOTE line, however many tickets name the cause."""
        out = sweep(named_world(THREE)).out
        lines_are(out, "PROMOTE", [SAID])
        assert_that(len(mentioning(out, "PROMOTE")), equal_to(1))

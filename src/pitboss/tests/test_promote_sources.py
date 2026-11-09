"""The mentions are counted in every ticket and PR, whatever its state (#388).

The cause: the count read the bodies of the queued tickets and the open PRs, so a
naming ticket that got a PR, lost its label or was closed dropped out of K.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to

from . import fakes, rankworld, world
from .test_promote import NINTH, PROJECT, SAID, THREE, TICKETS, named_world

FIRST_THREE = ["owner/project#1", "owner/project#3", NINTH]


def promoted(here: world.World) -> None:
    """Require the line of ticket 9 with three corrections, and its rank."""
    rankworld.printed(here, "PROMOTE", [SAID])
    ranked = f"{NINTH} (start a PR p0, opened 2026-09-01,"
    assert_that(rankworld.next_output(here), contains_string(ranked))


class TestEveryTicketAndPull(unittest.TestCase):
    """What K counts."""

    def test_a_naming_ticket_under_an_open_pull_request_counts(self) -> None:
        """Ticket 11 has PR 3, whose body does not repeat the phrase: K is 3."""
        here = named_world(THREE)
        rankworld.fixing(here, 3, "Fixes #11")
        started = rankworld.starts(here)
        assert_that(started[:3], equal_to(FIRST_THREE))
        assert_that("owner/project#11" in started, equal_to(False))
        promoted(here)

    def test_a_closed_naming_ticket_counts(self) -> None:
        """Ticket 12 is closed: the three still name ticket 9."""
        here = named_world(THREE, states={12: "closed"})
        promoted(here)
        assert_that(rankworld.starts(here)[:3], equal_to(FIRST_THREE))

    def test_an_unlabelled_naming_ticket_counts(self) -> None:
        """Ticket 12 has no priority label, so it is not queued: it counts."""
        here = named_world(THREE, ranks={**TICKETS, 12: "docs"})
        promoted(here)

    def test_a_merged_pull_request_counts(self) -> None:
        """A merged PR that says ``Cause: #9`` is the third mention."""
        merged = {
            "number": 40,
            "state": "closed",
            "title": "Cause: #9",
            "body": "",
            "pull_request": {"merged_at": "2026-10-01T00:00:00Z"},
        }
        here = named_world({10: "Caused by #9", 11: "Cause: #9"})
        listing = here.bodies[fakes.page(f"{PROJECT}/issues?state=all")]
        assert isinstance(listing, list)
        listing.append(merged)
        said = (
            "PROMOTE owner/project#9 to p0: caused 3 corrections"
            " (owner/project#10, owner/project#11, owner/project#40)"
        )
        rankworld.printed(here, "PROMOTE", [said])

    def test_the_listing_is_read_once_for_each_repository(self) -> None:
        """One paginated call for each configured repository, not one per ticket."""
        here = named_world(THREE)
        rankworld.next_output(here)
        asked = [each[-1] for each in here.calls if "issues?state=all" in each[-1]]
        every = [PROJECT, world.LIBRARY]
        expected = [fakes.page(f"{each}/issues?state=all") for each in every]
        assert_that(asked, equal_to(expected))

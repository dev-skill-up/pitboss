"""Plan 6.3: the tickets of a label are read only as far as the walk needs them."""

import re
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from . import fakes, sceneruns
from . import world as scenes

PROJECT = scenes.PROJECT
LABEL_SEARCH = re.compile(r"^search/issues\?q=org:\S+\+label:urgent")
TICKET_READ = re.compile(r"^repos/owner/project/issues/\d+$")
NEXT_LINE = re.compile(r"^NEXT \d+ of 5\. \w+: ")


def world_with(*changes: Mapping[str, object]) -> scenes.World:
    """The scene's world with canned bodies replaced or added.

    Args:
        *changes: the bodies.

    Returns:
        The world.
    """
    here = scenes.make_world()
    for each in changes:
        here.bodies.update(each)
    return here


def no_pull_requests() -> scenes.World:
    """A world whose repositories have no open pull request and 8 tickets.

    Returns:
        The world.
    """
    numbers = range(20, 28)
    rows = [{**scenes.TICKET, "number": n, "title": f"Ticket {n}"} for n in numbers]
    return world_with(
        {
            fakes.page(f"{slug}/pulls?state=open"): []
            for slug in (PROJECT, scenes.LIBRARY)
        },
        dict.fromkeys([fakes.page(f"{PROJECT}/issues?state=open&labels=urgent")], rows),
        {f"{PROJECT}/issues/{n}": {"state": "open", "title": "T"} for n in numbers},
    )


def five_pull_requests() -> scenes.World:
    """A world with 5 startable pull requests (the conflicted ones need a worker).

    Returns:
        The world.
    """
    more = (5, 6, 7)
    pulls = [fakes.pull_body(n) for n in (1, 2, 3, *more)]
    dirty = [scenes.pull_bodies(PROJECT[6:], n, [scenes.RED], "dirty") for n in more]
    return world_with({fakes.page(f"{PROJECT}/pulls?state=open"): pulls}, *dirty)


def slots_next(here: scenes.World, pattern: re.Pattern[str]) -> Sequence[int]:
    """Run ``slots next`` in a world and count what it asked.

    Args:
        here: the world.
        pattern: the paths to count.

    Returns:
        The number of ``NEXT`` lines printed, of paths the pattern matches, and of
        those that are no first page.
    """
    out = sceneruns.command_in(here, "slots", "next").out
    lines = [each for each in out.splitlines() if NEXT_LINE.match(each)]
    found = [each for each in sceneruns.request_paths(here) if pattern.match(each)]
    return [len(lines), len(found), len([x for x in found if "&page=1" not in x])]


class TestLabelWalk(unittest.TestCase):
    """Plan 6.3: a label is searched once, and only the tickets needed are read."""

    def test_6_3_no_pull_request_asks_one_first_page_and_five_tickets(self) -> None:
        """Five decisions from 8 tickets: one first page of the label, 5 tickets."""
        searched = slots_next(no_pull_requests(), LABEL_SEARCH)
        read = slots_next(no_pull_requests(), TICKET_READ)
        assert_that((searched, read[1]), equal_to(([5, 1, 0], 5)))

    def test_6_3_five_pull_requests_search_no_label(self) -> None:
        """Five decisions from pull requests: no priority label is searched."""
        assert_that(slots_next(five_pull_requests(), LABEL_SEARCH), equal_to([5, 0, 0]))

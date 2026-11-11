"""``slots next`` reads the top of the queue, not all of it (keyword: ticket-window).

The cause: the full ``slots next`` paged through every open item of every
repository, 167 s for the real queue (pitboss#443). The first tickets of the
order are the oldest of each priority label; the listing is sorted, so a queue
ten times as long is read in as many pages.
"""

import contextlib
import io
import pathlib
import unittest
from typing import Mapping, MutableMapping, Sequence

from hamcrest import assert_that, contains_string, equal_to, greater_than, has_length

from .. import causecache, config, ghapi, slotcache, ticketwindow, windowrun
from . import fakes, test_holds, test_promote, test_work_order, world
from .says import lacks, says
from .test_slot_commands import next_output

PROJECT = world.PROJECT
URGENT = f"{PROJECT}/issues?state=open&labels=urgent"
LOW = f"{PROJECT}/{test_work_order.OPEN}&labels=low"
P0 = f"{PROJECT}/issues?state=open&labels=p0"
REPOSITORY = config.make_repo("owner", "project")
LONG = windowrun.WINDOW + 6
ENDS = "The list ends at its first"
HELD = "HELD (no new pull requests in owner/project: 3 open)"


def tickets(first: int, last: int, label: str) -> Sequence[Mapping[str, object]]:
    """Tickets with a label, oldest first.

    Args:
        first: the first number.
        last: one past the last number.
        label: their label.

    Returns:
        The raw tickets.
    """
    return [
        {
            "number": each,
            "title": f"Ticket {each}",
            "created_at": f"2026-08-01T00:{each % 60:02d}:00+00:00",
            "labels": [{"name": label}],
        }
        for each in range(first, last)
    ]


def pages_read(queue: int) -> Sequence[str]:
    """The lists a full ``slots next`` reads when the low priority has a queue.

    Args:
        queue: how many pages of 100 low-priority tickets the project has.

    Returns:
        The paths of the lists it asked for (each has ``page=``).
    """
    here = test_work_order.ordered_world()
    for page in range(1, queue + 1):
        first = 1000 + 100 * page
        here.bodies[fakes.page(LOW, page)] = tickets(first, first + 100, "low")
    before = len(here.calls)
    next_output(here)
    asked = [each[-1] for each in here.calls[before:] if "api" in each]
    return [each for each in asked if "page=" in each]


class TestThePagesRead(unittest.TestCase):
    """The pages read stay the same when the queue holds ten times as many."""

    def test_ten_times_the_low_ranked_items_are_read_in_the_same_pages(self) -> None:
        """One page of the low priority is read, whether it has 1 page or 10."""
        small, large = pages_read(1), pages_read(10)
        assert_that(sorted(large), equal_to(sorted(small)))
        assert_that(small, has_length(greater_than(0)))
        assert_that("\n".join(large).count("labels=low"), equal_to(2))

    def test_the_window_reads_the_next_page_when_the_merge_needs_it(self) -> None:
        """A window of 150 reads 2 pages of 105 tickets; one of 3 reads 1."""
        base = "repos/owner/project/issues?state=open&labels=low"
        asked = ticketwindow.Asked(repos=[REPOSITORY], labels=["low"], skip=set())
        for count, found, calls in [(150, 105, 2), (3, 3, 1)]:
            with self.subTest(count):
                bodies: MutableMapping[str, object] = {
                    fakes.page(base, 1): tickets(1, 101, "low"),
                    fakes.page(base, 2): tickets(101, 106, "low"),
                }
                fake = fakes.FakeProcesses(bodies=bodies)
                github = ghapi.GitHub(run=fake, mutate=fake)
                window = ticketwindow.window(github, asked, count)
                assert_that((len(window), len(fake.calls)), equal_to((found, calls)))


def long_queue() -> world.World:
    """A world where ticket 9 is named by three, and the top priority has a queue.

    Returns:
        The world.
    """
    here = test_promote.named_world(test_promote.THREE)
    here.bodies[fakes.page(P0)] = tickets(100, 100 + LONG, "p0")
    return here


class TestAWindowThatGrows(unittest.TestCase):
    """The tickets read grow while too few items are offered."""

    def test_a_held_project_reads_past_the_first_window(self) -> None:
        """30 held tickets: the first window shows none of the last, the next does."""
        here = test_holds.held_world(test_holds.PROJECT_TABLE)
        test_holds.serve(here, URGENT, tickets(200, 200 + LONG, "urgent"))
        shown = next_output(here)
        says(shown, f"{HELD} owner/project#{200 + LONG - 1}")
        lacks(shown, ENDS)

    def test_a_queue_longer_than_the_window_says_where_the_list_ends(self) -> None:
        """Enough items are offered: the window stops and the list says so."""
        says(next_output(long_queue()), ENDS, test_promote.SAID)


def cache_of(here: world.World) -> pathlib.Path:
    """Where the world keeps what ``slots next`` remembers.

    Args:
        here: the world.

    Returns:
        The cache's file.
    """
    return slotcache.path_of(here.ledger)


class TestTheCache(unittest.TestCase):
    """What is kept between runs is a copy: bad copies are read again."""

    def test_a_cache_that_is_not_an_object_or_cannot_be_written_is_empty(self) -> None:
        """A missing directory, and a file that holds a list."""
        gone = pathlib.Path("/nonexistent/pitboss/cache.json")
        slotcache.write(gone, {"a": 1})
        listed = cache_of(world.make_world())
        listed.write_text("[1, 2]", encoding="utf-8")
        found = [dict(slotcache.read(gone)), dict(slotcache.read(listed))]
        assert_that(found, equal_to([{}, {}]))

    def test_a_cache_that_cannot_be_written_is_said_on_standard_error(self) -> None:
        """The file and the error are named."""
        gone = pathlib.Path("/nonexistent/pitboss/cache.json")
        said = io.StringIO()
        with contextlib.redirect_stderr(said):
            slotcache.write(gone, {"a": 1})
        assert_that(said.getvalue(), contains_string(str(gone)))
        assert_that(said.getvalue(), contains_string("cannot be written"))

    def test_entries_that_are_not_what_was_kept_are_read_afresh(self) -> None:
        """Junk, and an entry with no time, are an empty entry."""
        for junk in ("text", {"named": [], "since": 1}, {"named": {"1": ["a#1"]}}):
            with self.subTest(str(junk)):
                assert_that(causecache.entry_of(junk), equal_to(("", {})))

    def test_a_run_over_junk_in_the_cache_still_lists_the_order(self) -> None:
        """The causes are read again and the cache is made whole."""
        here = test_promote.named_world(test_promote.THREE)
        slotcache.write(cache_of(here), {causecache.CAUSES: {"owner/project": "junk"}})
        shown = next_output(here)
        says(shown, test_promote.SAID)
        kept = slotcache.read(cache_of(here))[causecache.CAUSES]
        assert isinstance(kept, dict)
        assert_that(sorted(kept), equal_to(["owner/lib", "owner/project"]))

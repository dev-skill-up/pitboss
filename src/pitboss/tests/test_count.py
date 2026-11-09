"""Tests for ``pitboss count``: the open tickets by priority (pitboss#281)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to

from .. import ticketcount
from . import fakes, ownerbodies, world

OPEN = "issues?state=open"


def _ticket(number: int, title: str, *labels: str) -> Mapping[str, object]:
    return {
        "number": number,
        "title": title,
        "created_at": "2026-09-01T00:00:00+00:00",
        "labels": [{"name": label} for label in labels],
    }


PULL_REQUEST: Mapping[str, object] = {
    **_ticket(3, "A pull request", "p0"),
    "pull_request": {},
}
PROJECT = [
    _ticket(5, "Triage", "bug"),
    _ticket(1, "Crash", "p0", "bug"),
    _ticket(2, "Slow", "p1"),
    PULL_REQUEST,
    _ticket(4, "Idle", "p3"),
    _ticket(6, "Both", "p2", "p0"),
    _ticket(7, "Far", "p4"),
]
LIBRARY = [_ticket(1, "Lib slow", "p1"), _ticket(2, "Lib later", "p2")]
EXTRA = [_ticket(3, "Extra later", "p2"), _ticket(4, "Extra down", "p0")]

FULL = """\
p0
  owner/project: 2
  owner/lib: 0
  owner/extra: 1
  total: 3
  owner/project#1 Crash
  owner/project#6 Both
  owner/extra#4 Extra down
p1
  owner/project: 1
  owner/lib: 1
  owner/extra: 0
  total: 2
  owner/project#2 Slow
  owner/lib#1 Lib slow
p2
  owner/project: 0
  owner/lib: 1
  owner/extra: 1
  total: 2
  owner/lib#2 Lib later
  owner/extra#3 Extra later
p3
  owner/project: 1
  owner/lib: 0
  owner/extra: 0
  total: 1
  owner/project#4 Idle
unlabelled
  owner/project: 2
  owner/lib: 0
  owner/extra: 0
  total: 2
  owner/project#5 Triage
  owner/project#7 Far
"""
ONLY_P1 = """\
p1
  owner/project: 1
  owner/lib: 1
  owner/extra: 0
  total: 2
  owner/project#2 Slow
  owner/lib#1 Lib slow
"""


def counting() -> world.World:
    """A world of three repositories with tickets at p0, p1, p2 and p3.

    Returns:
        The world: ``project``, ``lib`` and ``extra``, whose open issues are the
        constants above (the project's list also holds a PR labeled p0).
    """
    here = world.make_world()
    here.bodies[ownerbodies.LISTING] = ownerbodies.listed(("owner/extra", False))
    here.bodies.update(ownerbodies.extra())
    here.bodies.update(fakes.bodies_under(world.PROJECT, [(OPEN, PROJECT)]))
    here.bodies.update(fakes.bodies_under(world.LIBRARY, [(OPEN, LIBRARY)]))
    here.bodies.update(fakes.bodies_under(ownerbodies.EXTRA, [(OPEN, EXTRA)]))
    return here


class TestCount(unittest.TestCase):
    """``pitboss count CONFIG [PRIORITY]``."""

    def test_prints_every_priority_of_every_repository(self) -> None:
        """A line for each repository and the total of each priority, then its tickets."""
        done = world.again(counting(), "count")
        assert_that((done.out, done.code), equal_to((FULL, 0)))

    def test_a_priority_prints_only_that_priority(self) -> None:
        """``count CONFIG p1`` has the p1 counts and list and nothing else."""
        done = world.again(counting(), "count", "p1")
        assert_that((done.out, done.code), equal_to((ONLY_P1, 0)))

    def test_the_config_option_and_a_priority(self) -> None:
        """The priority is the same word after ``--config``."""
        here = counting()
        done = world.invoke(here, "count", "--config", here.config, "p1")
        assert_that((done.out, done.code), equal_to((ONLY_P1, 0)))

    def test_a_pull_request_is_no_ticket(self) -> None:
        """The labeled PR of the list is not counted."""
        done = world.again(counting(), "count", "p0")
        assert_that("A pull request" in done.out, equal_to(False))

    def test_refuses_a_word_that_is_no_priority(self) -> None:
        """Nothing is printed or read for ``p4`` or ``unlabelled``."""
        here = counting()
        for word in ("p4", "unlabelled"):
            with self.subTest(word):
                done = world.again(here, "count", word)
                assert_that(
                    (done.out, done.code, "count takes a priority" in done.err),
                    equal_to(("", 2, True)),
                )

    def test_a_repository_it_cannot_read_ends_incomplete(self) -> None:
        """The count says what it did not read and exits 1."""
        here = counting()
        del here.bodies[ownerbodies.EXTRA]
        done = world.again(here, "count", "p1")
        assert_that(
            ("INCOMPLETE" in done.out + done.err, done.code), equal_to((True, 1))
        )

    def test_the_help_text_says_where_the_owner_count_comes_from(self) -> None:
        """A count given to the owner comes from this command, the owner's words."""
        done = world.invoke(world.make_world(), "count", "--help")
        assert_that(
            " ".join(done.out.split()),
            contains_string(
                "A count of tickets given to the owner comes from this command"
                " (Moshe, 2026-11-06: count p0, p1 and p2, and filter when the"
                " question names one)"
            ),
        )


class TestPriority(unittest.TestCase):
    """The priority a ticket is counted at."""

    def test_the_highest_label_of_p0_to_p3(self) -> None:
        """Other labels and other ``pN`` count for nothing."""
        cases = [
            (["p2", "p0"], "p0"),
            (["p3"], "p3"),
            (["p4", "bug"], ticketcount.UNLABELLED),
            ([], ticketcount.UNLABELLED),
        ]
        for labels, expected in cases:
            with self.subTest(labels):
                assert_that(ticketcount.priority_of(labels), equal_to(expected))

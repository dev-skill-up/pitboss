"""Tests for ``pitboss count``: the open tickets by priority (pitboss#281)."""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to

from .. import ticketcount
from . import fakes, ownerbodies, world

OPEN = "issues?state=open"
OWNER_RULE = (
    "A count of tickets given to the owner comes from this command"
    " (Moshe, 2026-11-06: count p0, p1 and p2, and filter when the question names"
    " one)"
)


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


def printed(*words: str) -> tuple[str, object]:
    """Run ``count`` in the world of three repositories.

    Args:
        *words: the words after the configuration.

    Returns:
        What it printed and its exit code.
    """
    done = world.again(counting(), "count", *words)
    return done.out, done.code


def printed_with_option(*words: str) -> tuple[str, object]:
    """Run ``count`` with the configuration given as ``--config``.

    Args:
        *words: the words after it.

    Returns:
        What it printed and its exit code.
    """
    here = counting()
    done = world.invoke(here, "count", "--config", here.config, *words)
    return done.out, done.code


def ended_without_extra(*words: str) -> tuple[object, bool]:
    """Run ``count`` in a world where the repository ``extra`` cannot be read.

    Args:
        *words: the words after the configuration.

    Returns:
        Its exit code, and whether it said ``INCOMPLETE``.
    """
    here = counting()
    del here.bodies[ownerbodies.EXTRA]
    done = world.again(here, "count", *words)
    return done.code, "INCOMPLETE" in done.out + done.err


def refusal(word: str) -> bool:
    """Say whether ``count`` refuses a word on standard error.

    Args:
        word: the word after the configuration.

    Returns:
        True when it says what it takes.
    """
    return "count takes a priority" in world.again(counting(), "count", word).err


def usage_of(command: str) -> str:
    """The usage text of a command, on one line.

    Args:
        command: the command.

    Returns:
        What ``--help`` prints, its white space single.
    """
    return " ".join(world.invoke(world.make_world(), command, "--help").out.split())


class TestCount(unittest.TestCase):
    """``pitboss count CONFIG [PRIORITY]``."""

    def test_prints_what_the_priority_names(self) -> None:
        """No word: every priority, a line for each repository, the total, the list.

        ``p1``: only the p1 counts and list; the pull request labeled p0 of the
        project's list is no ticket and is counted nowhere.
        """
        cases = [((), FULL), (("p1",), ONLY_P1)]
        found = [printed(*words) for words, _ in cases]
        assert_that(found, equal_to([(shown, 0) for _, shown in cases]))

    def test_the_priority_follows_the_config_option(self) -> None:
        """The priority is the same word after ``--config``."""
        assert_that(printed_with_option("p1"), equal_to((ONLY_P1, 0)))

    def test_refuses_a_word_that_is_no_priority(self) -> None:
        """Nothing is printed for ``p4`` or ``unlabelled``."""
        words = ("p4", "unlabelled")
        found = [(*printed(word), refusal(word)) for word in words]
        assert_that(found, equal_to([("", 2, True)] * len(words)))

    def test_a_repository_it_cannot_read_ends_incomplete(self) -> None:
        """The count says what it did not read and exits 1."""
        assert_that(ended_without_extra("p1"), equal_to((1, True)))

    def test_the_usage_says_where_the_owner_count_comes_from(self) -> None:
        """A count given to the owner comes from this command, the owner's words."""
        assert_that(OWNER_RULE in usage_of("count"), equal_to(True))


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

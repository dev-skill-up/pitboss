"""The ticket reader, closed-world, and what ``act ticket`` writes.

The keyword is ticket-reader, pitboss#444.
"""

import functools
import unittest

from hamcrest import assert_that, equal_to

from .. import ticketreader
from .says import raises_with


def _refused(body: str | None, said: str) -> None:
    raises_with(ticketreader.Refused, said, functools.partial(ticketreader.items, body))


def _read(body: str, items: list[str]) -> None:
    assert_that(list(ticketreader.items(body)), equal_to(items))


class TestItems(unittest.TestCase):
    """The forms of a Done-when section."""

    def test_444_a_list_its_continuations_and_its_keys(self) -> None:
        """An introduction, items of each mark, a continued line.

        Then a key that ends them, then a rule.
        """
        body = (
            "## Done when\n\nIntro.\n\n- a\n  more\n* b\n1. c\nPaths: src/\n- not an"
            " item\n---\nafter\n"
        )
        _refused(body, "neither an item")
        body = (
            "## Done when\n\nIntro.\n\n- a\n  more\n* b\n1. c\nPaths: src/\n---\n-"
            " after\n"
        )
        _read(body, ["a more", "b", "c"])

    def test_444_paragraphs_when_there_is_no_list(self) -> None:
        """Each paragraph is an item; a key paragraph is not.

        The next heading ends them.
        """
        body = (
            "## Done-when\n\nfirst\nline\n\nsecond\n\nPriority: p1\n## Other\nthird\n"
        )
        _read(body, ["first line", "second"])

    def test_444_the_refusals(self) -> None:
        """No heading, two, no item, a stray line."""
        _refused(None, "0 `## Done when`")
        _refused("## Done when\n- a\n## Done when\n- b\n", "2 `## Done when`")
        _refused("## Done when\n\nPaths: x\n", "no Done-when item")
        _refused("## Done when\n- a\nloose\n", "neither an item")

    def test_444_what_act_ticket_writes_is_read_back(self) -> None:
        """The writer's items are the reader's."""
        body = ticketreader.written(["a demonstrated by b", "c"], ["src/"], 100, "p1")
        _read(body, ["a demonstrated by b", "c"])


class TestClosing(unittest.TestCase):
    """Which PRs close a ticket."""

    def test_444_every_closing_keyword_and_form(self) -> None:
        """A short and a full reference close.

        Another repository's and another number do not.
        """
        bodies = [
            (1, "Fixes #4"),
            (2, "resolved: o/r#4"),
            (3, "Closes x/y#4"),
            (4, "fix #40"),
            (5, None),
        ]
        assert_that(list(ticketreader.started(bodies, "o/r", 4)), equal_to([1, 2]))

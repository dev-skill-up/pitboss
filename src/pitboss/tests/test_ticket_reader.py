"""The ticket reader, closed-world, and what ``act ticket`` writes.

The keyword is ticket-reader, pitboss#444.
"""

import unittest

from hamcrest import assert_that, contains_string, equal_to, instance_of

from .. import ticketreader


def _refused(body: str | None, said: str) -> None:
    found = ticketreader.done_when(body)
    assert_that(found, instance_of(ticketreader.NotInForm))
    assert_that(str(getattr(found, "problem", "")), contains_string(said))


def _read(body: str, items: list[str]) -> None:
    assert_that(ticketreader.done_when(body), equal_to(ticketreader.Items(found=items)))


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

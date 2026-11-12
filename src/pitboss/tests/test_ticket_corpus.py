"""A Done-when item comes only from the Done-when list.

The keyword is done-when-bullets, bats#654.

The corpus is the bodies of real tickets (``tests/tickets``): bats#653 ended with
"Found by quire#1118." and plan-check demanded it word for word as an item.
"""

import pathlib
import re
import unittest

from hamcrest import assert_that, contains_exactly, equal_to, is_

from .. import ticketwhen
from ..textparts import having

CORPUS = pathlib.Path(__file__).with_name("tickets")
COUNTS = {
    "bats-lang-bats-444": 4,
    "bats-lang-bats-653": 2,
    "bats-lang-quire-1109": 3,
    "bats-lang-quire-1113": 2,
    "bats-lang-quire-1118": 2,
    "bats-lang-repository-prototype-588": 1,
    "bats-lang-repository-prototype-681": 3,
}
BULLET = re.compile(
    r"^\s*(?:(?:[-*+]|\d{1,3}[.)])\s+|Done[- ]when\s*:\s*)(.*)$", re.IGNORECASE
)

# a lead line states for every item and is read; no list: paragraphs are items;
# a deeper bullet belongs to its item, and a trailing link is no item
SHAPES = (
    (
        "## Done when\n\nEach item is demonstrated by Y.\n\n- a\n- b\n\nFound by"
        " x.\n",
        ("Each item is demonstrated by Y.", "a", "b"),
    ),
    (
        "## Done when\n\nFirst thing.\n\nSecond thing.\n",
        ("First thing.", "Second thing."),
    ),
    (
        "## Done when\n\n- one\n  - nested\n- two\n\n"
        "See https://example.org/x\n\n## Notes\n\n- not an item\n",
        ("one - nested", "two"),
    ),
)


def body(name: str) -> str:
    """A ticket of the corpus.

    Args:
        name: its file's name without the extension.

    Returns:
        Its body as it was read.
    """
    return (CORPUS / f"{name}.txt").read_text(encoding="utf-8")


class TestCorpus(unittest.TestCase):
    """The real bodies, item counts and texts."""

    def test_c33_every_ticket_has_its_items_counted(self) -> None:
        """The counts of the corpus; a new file must be listed."""
        found = sorted(each.stem for each in CORPUS.glob("*.txt"))
        assert_that(found, equal_to(sorted(COUNTS)))
        for name, count in COUNTS.items():
            assert_that(len(ticketwhen.items(body(name))), equal_to(count), name)

    def test_c33_no_paragraph_of_a_ticket_is_an_item(self) -> None:
        """Every item starts a bullet of the ticket: no origin line, no note."""
        for name in COUNTS:
            starts = [
                found[1]
                for each in body(name).splitlines()
                if (found := BULLET.match(each))
            ]
            for item in ticketwhen.items(body(name)):
                assert_that(
                    any(item.startswith(each.strip()[:40]) for each in starts),
                    is_(True),
                    f"{name}: {item[:60]}",
                )

    def test_c33_the_origin_line_of_bats_653_is_not_an_item(self) -> None:
        """The case of bats#654."""
        items = ticketwhen.items(body("bats-lang-bats-653"))
        assert_that(having(items, "Found by"), equal_to([]))

    def test_c33_trailing_notes_of_the_other_tickets_are_not_items(self) -> None:
        """Avenue, priority and not-in-this-ticket paragraphs are context."""
        for name in ("bats-lang-quire-1109", "bats-lang-quire-1118"):
            for item in ticketwhen.items(body(name)):
                for note in ("Priority:", "Avenue exhausted", "Not in this ticket"):
                    assert_that(item.startswith(note), is_(False), name)


class TestShapes(unittest.TestCase):
    """Each shape the parser sees."""

    def test_c33_each_shape_is_read(self) -> None:
        """A lead line is kept, paragraphs are items, a nested bullet stays in its."""
        for ticket, expected in SHAPES:
            with self.subTest(ticket):
                assert_that(ticketwhen.items(ticket), contains_exactly(*expected))

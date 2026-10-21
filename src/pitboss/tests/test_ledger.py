"""Tests for the slot ledger."""

import pathlib
import tempfile
import unittest

from hamcrest import assert_that, calling, contains_exactly, equal_to, raises

from .. import config, ledger

PROJECT = config.Repo(owner="o", name="r")
SPECS = (
    config.SlotSpec(name="first", model="small"),
    config.SlotSpec(name="second", model="large"),
)
MODELS = ("small", "large")


class TestLedger(unittest.TestCase):
    """Changing the ledger."""

    def setUp(self) -> None:
        """Start a ledger from the configured slots."""
        self.path = pathlib.Path(tempfile.mkdtemp()) / "deep" / "ledger.json"
        self.book = ledger.read(self.path, SPECS)

    def test_round_trip(self) -> None:
        """A written ledger reads back the same."""
        book = ledger.take(self.book, "first", "agent-1", "o/r#5")
        book = ledger.record_failure(book, "o/r#5", "small")
        book = ledger.record_failure(book, "o/r#5", "small")
        ledger.write(self.path, book)
        assert_that(ledger.read(self.path, ()), equal_to(book))
        assert_that(book.failed, equal_to({"o/r#5": ("small",)}))

    def test_take_refuses_an_occupied_slot(self) -> None:
        """An occupied slot is freed before it is taken again."""
        book = ledger.take(self.book, "first", "agent-1", "o/r#5")
        assert_that(
            calling(ledger.take).with_args(book, "first", "agent-2", "o/r#6"),
            raises(ledger.LedgerError, "free it first"),
        )
        book = ledger.free(book, "first")
        book = ledger.take(book, "first", "agent-2", "o/r#6")
        assert_that(ledger.find(book, "first").agent, equal_to("agent-2"))

    def test_add_and_remove(self) -> None:
        """Slots are added and removed; an occupied one is not removed."""
        book = ledger.add(self.book, config.SlotSpec(name="third", model="small"), MODELS)
        assert_that([slot.name for slot in book.slots], equal_to(["first", "second", "third"]))
        for spec, word in [
            (config.SlotSpec(name="third", model="small"), "already exists"),
            (config.SlotSpec(name="fourth", model="huge"), "not one of"),
        ]:
            assert_that(
                calling(ledger.add).with_args(book, spec, MODELS),
                raises(ledger.LedgerError, word),
            )
        book = ledger.take(book, "third", "agent", "task")
        assert_that(
            calling(ledger.remove).with_args(book, "third"),
            raises(ledger.LedgerError, "free it first"),
        )
        book = ledger.remove(book, "second")
        assert_that([slot.name for slot in book.slots], equal_to(["first", "third"]))

    def test_unknown_slot(self) -> None:
        """An unknown slot is named with the slots there are."""
        assert_that(
            calling(ledger.free).with_args(self.book, "nope"),
            raises(ledger.LedgerError, "first, second"),
        )
        empty = ledger.Ledger(slots=(), failed={})
        assert_that(
            calling(ledger.find).with_args(empty, "nope"),
            raises(ledger.LedgerError, "none"),
        )

    def test_gone(self) -> None:
        """A slot whose agent is not running is gone."""
        book = ledger.take(self.book, "first", "agent-1", "t")
        book = ledger.take(book, "second", "agent-2", "t")
        gone = ledger.gone(book, ["agent-2"])
        assert_that([slot.name for slot in gone], contains_exactly("first"))


class TestReference(unittest.TestCase):
    """Spelling references in full."""

    def test_forms(self) -> None:
        """Every short form is spelled in full; anything else is kept."""
        cases = {
            "#5": "o/r#5",
            "lib#5": "o/lib#5",
            "x/lib#5": "x/lib#5",
            "a task": "a task",
        }
        for text, expected in cases.items():
            assert_that(ledger.reference(text, PROJECT), equal_to(expected))

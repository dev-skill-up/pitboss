"""Tests for the slot ledger."""

import unittest
from typing import Mapping, Protocol, Sequence

from hamcrest import assert_that, equal_to

from .. import config, ledger
from . import fakes

PROJECT = config.make_repo("o", "r")
SPECS = (
    config.SlotSpec(name="first", model="small"),
    config.SlotSpec(name="second", model="large"),
)
MODELS = ("small", "large")
Outcome = ledger.Ledger | ledger.Refusal


class Operation(Protocol):
    """A change to the ledger, from words."""

    def __call__(self, book: ledger.Ledger, *words: str) -> Outcome:
        """Change the ledger.

        Args:
            book: the ledger.
            *words: the change's words.

        Returns:
            The new ledger, or a refusal.
        """


def _take(book: ledger.Ledger, *words: str) -> Outcome:
    slot, agent, task = words
    return ledger.take(book, slot, agent, task)


def _add(book: ledger.Ledger, *words: str) -> Outcome:
    name, model, *configured = words
    return ledger.add(book, config.SlotSpec(name=name, model=model), configured)


def _fail(book: ledger.Ledger, *words: str) -> Outcome:
    ticket, model = words
    return ledger.record_failure(book, ticket, model)


def _free(book: ledger.Ledger, *words: str) -> Outcome:
    return ledger.free(book, *words[:1])


def _remove(book: ledger.Ledger, *words: str) -> Outcome:
    return ledger.remove(book, *words[:1])


OPERATIONS: Mapping[str, Operation] = {
    "take": _take,
    "free": _free,
    "add": _add,
    "remove": _remove,
    "fail": _fail,
}
CASES: Sequence[tuple[Sequence[Sequence[str]], object]] = [
    ([("take", "first", "a1", "t")], [("first", "a1"), ("second", "")]),
    (
        [("take", "first", "a1", "t"), ("take", "first", "a2", "t")],
        "slot first holds a1 on t: free it first",
    ),
    (
        [("take", "first", "a1", "t"), ("free", "first")],
        [("first", ""), ("second", "")],
    ),
    (
        [("add", "third", "small", *MODELS), ("remove", "second")],
        [("first", ""), ("third", "")],
    ),
    ([("add", "first", "small", *MODELS)], "slot first already exists"),
    (
        [("add", "third", "small")],
        "model 'small' is not one of none: set [slots] models",
    ),
    (
        [("take", "second", "a1", "t"), ("remove", "second")],
        "slot second holds a1: free it first",
    ),
    ([("free", "nope")], "no slot 'nope' (slots: first, second)"),
    ([("remove", "nope"), ("free", "first")], "no slot 'nope' (slots: first, second)"),
    (
        [("remove", "first"), ("remove", "second"), ("take", "x", "a", "t")],
        "no slot 'x' (slots: none)",
    ),
]
ROUND_TRIP = [("take", "first", "a1", "o/r#5"), *[("fail", "o/r#5", "small")] * 2]
REFERENCES = {
    "#5": "o/r#5",
    "lib#5": "o/lib#5",
    "x/lib#5": "x/lib#5",
    "a task": "a task",
}


def apply(changes: Sequence[Sequence[str]]) -> Outcome:
    """Apply changes to a new ledger; a refusal is kept to the end.

    Args:
        changes: each change's operation, then its words.

    Returns:
        The last ledger, or the refusal.
    """
    current: Outcome = ledger.read(fakes.directory() / "absent", SPECS)
    for operation, *words in changes:
        if isinstance(current, ledger.Ledger):
            current = OPERATIONS[operation](current, *words)
    return current


def names(outcome: Outcome) -> object:
    """The slot names and agents of a ledger, or the reason of a refusal.

    Args:
        outcome: the ledger or the refusal.

    Returns:
        The names, or the reason.
    """
    if isinstance(outcome, ledger.Refusal):
        return outcome.reason
    return [(slot.name, slot.agent) for slot in outcome.slots]


class TestChanges(unittest.TestCase):
    """Changing the ledger, and what it refuses."""

    def test_changes(self) -> None:
        """Each change gives its ledger or its refusal."""
        found = [names(apply(changes)) for changes, _ in CASES]
        assert_that(found, equal_to([expected for _, expected in CASES]))

    def test_round_trip(self) -> None:
        """A written ledger reads back the same, failures and all."""
        path = fakes.directory() / "deep" / "ledger.json"
        book = apply(ROUND_TRIP)
        assert isinstance(book, ledger.Ledger)
        ledger.write(path, book)
        gone = [slot.name for slot in ledger.gone(book, ["a2"])]
        found = (ledger.read(path, ()) == book, book.failed, gone)
        assert_that(found, equal_to((True, {"o/r#5": ("small",)}, ["first"])))

    def test_references(self) -> None:
        """Every short form is spelled in full; anything else is kept."""
        found = {text: ledger.reference(text, PROJECT) for text in REFERENCES}
        assert_that(found, equal_to(REFERENCES))

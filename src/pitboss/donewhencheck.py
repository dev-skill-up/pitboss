"""The Done-when of pitboss#444 as a pairing: each item's tests exist.

``donewhen.tsv`` pairs each item of the ticket's Done-when with the tests that
demonstrate it: a rule id of the register (all of that row's tests) or a test
``module.name``. The check holds when every item names tests and each exists; that
they pass on the head is the test run, and that they fail on the base is
``pitboss base-check`` (keyword: done-when-check). The module runs nothing.
"""

import dataclasses
from typing import Callable, Sequence

from . import rules

Verdict = Callable[[str], bool]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Item:
    """One item of the Done-when.

    Attributes:
        number: its number in the ticket.
        tokens: the rule ids and tests that demonstrate it.
    """

    number: str
    tokens: Sequence[str]


def parse(text: str) -> Sequence[Item]:
    """Read the pairing.

    Args:
        text: lines of ``number``, a tab and the tokens separated by spaces.

    Returns:
        The items.
    """
    split = [each.split("\t") for each in text.splitlines() if each.strip()]
    return [Item(number=number, tokens=tokens.split()) for number, tokens in split]


def tests_of(item: Item, rows: Sequence[rules.Row]) -> Sequence[str]:
    """The tests an item names, a rule id read as the tests of its row.

    Args:
        item: the item.
        rows: the register's rows.

    Returns:
        The tests; an id with no row or no checked kind gives itself, which no test
        has as a name.
    """
    held = {each.id: each for each in rows if each.kind in rules.CHECKED}
    return [
        test
        for token in item.tokens
        for test in (held[token].tests if token in held else [token])
    ]


def missing(
    items: Sequence[Item], rows: Sequence[rules.Row], exists: Verdict
) -> Sequence[str]:
    """What an item names that is not there: no tests, an unknown id, an unknown test.

    Args:
        items: the items.
        rows: the register's rows.
        exists: whether a test ``module.name`` is defined.

    Returns:
        A finding for each.
    """
    found = []
    for entry in items:
        tests = tests_of(entry, rows)
        found += [
            f"item {entry.number}: {t} is not there"
            for t in tests
            if not _is(t, exists)
        ]
        found += [f"item {entry.number}: names no test"] * (not tests)
    return found


def _is(test: str, exists: Verdict) -> bool:
    return "." in test and exists(test)

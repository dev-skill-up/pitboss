"""The Done-when of pitboss#444 as a check: each item's tests, on the head and a base.

``donewhen.tsv`` pairs each item of the ticket's Done-when with the tests that
demonstrate it: a rule id of the register (all of that row's tests) or a test
``module.name``. The check holds when, for every item, each named test exists and
passes on the head, and at least one fails on the base (keyword: done-when-check).
The module runs nothing: whether a test exists and passes is given.
"""

import dataclasses
from typing import Callable, Mapping, Sequence

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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Checks:
    """What is known of the tests.

    Attributes:
        exists: whether a test ``module.name`` is there.
        head: whether it passes on the head.
        base: whether it passes on the base.
    """

    exists: Verdict
    head: Mapping[str, bool]
    base: Mapping[str, bool]


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
    for item in items:
        tests = tests_of(item, rows)
        found += [
            f"item {item.number}: {t} is not there" for t in tests if not _is(t, exists)
        ]
        found += [f"item {item.number}: names no test"] * (not tests)
    return found


def _is(test: str, exists: Verdict) -> bool:
    return "." in test and exists(test)


def refusals(
    items: Sequence[Item], rows: Sequence[rules.Row], checks: Checks
) -> Sequence[str]:
    """What keeps the Done-when from being demonstrated.

    Args:
        items: the items.
        rows: the register's rows.
        checks: what is known of the tests.

    Returns:
        The findings of ``missing``, a finding for each test that does not pass on
        the head, and for each item whose tests all pass on the base.
    """
    found = [*missing(items, rows, checks.exists)]
    for item in items:
        tests = [t for t in tests_of(item, rows) if _is(t, checks.exists)]
        found += [
            f"item {item.number}: {t} fails on the head"
            for t in tests
            if not checks.head.get(t, False)
        ]
        if tests and all(checks.base.get(t, False) for t in tests):
            found.append(f"item {item.number}: no named test fails on the base")
    return found

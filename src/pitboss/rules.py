"""The register of the owner's rules: each with its code and its tests (pitboss#444).

``rules.tsv`` has a row for every rule: ``id``, ``date``, ``kind``, ``words``,
``function`` (``module.name``) and ``tests`` (``test_module.test_name``, separated
by spaces). ``kind`` is ``enforced`` (a function and tests), ``output`` (a command
or printed line, and tests), ``outside`` (nothing pitboss can see) or ``open`` (a
rule not yet enforced: it is counted and listed, never hidden). ``rules check``
refuses a row with an unknown function, an unknown test, or a test that does not
name the rule's id (keyword: rules-register). The module reads no file: the
register's text and the readers of functions and tests are given.
"""

import collections
import dataclasses
import re
from typing import Callable, Sequence

KINDS = ("enforced", "output", "outside", "open")
FIELDS = 6
CHECKED = ("enforced", "output")
OUTSIDE = ("D4", "D12", "D13", "D14")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Row:
    """A rule of the register.

    Attributes:
        id: the rule's id (``A1``).
        date: when the owner said it.
        kind: one of ``KINDS``.
        words: the owner's words.
        function: the enforcing function, ``module.name``, or ``-``.
        tests: the tests, ``test_module.test_name``.
    """

    id: str
    date: str
    kind: str
    words: str
    function: str
    tests: Sequence[str]


FunctionKnown = Callable[[str], bool]
TestSource = Callable[[str], str | None]


def _row(fields: Sequence[str]) -> Row:
    return Row(
        id=fields[0],
        date=fields[1],
        kind=fields[2],
        words=fields[3],
        function=fields[4],
        tests=fields[5].split(),
    )


def parse(register: str) -> tuple[Sequence[Row], Sequence[str]]:
    """Read the register.

    Args:
        register: the register's text; ``#`` lines and blank lines are skipped.

    Returns:
        The rows, and a finding for each line that is no row.
    """
    split = [
        (number, each.split("\t"))
        for number, each in enumerate(register.splitlines(), 1)
        if each.strip() and each[0] != "#"
    ]
    bad = [
        f"bad-row: line {number} has {len(fields)} fields, not {FIELDS}"
        for number, fields in split
        if len(fields) != FIELDS
    ]
    return [_row(fields) for _, fields in split if len(fields) == FIELDS], bad


def names_id(test: str, rule: str) -> bool:
    """Whether a test's name has the rule's id as a word.

    Args:
        test: ``test_module.test_name``.
        rule: the id.

    Returns:
        True for ``test_a7_split`` and the id ``A7``; not for ``test_a70_x``.
    """
    name = test.split(".")[-1]
    return re.search(rf"(?:^|_){re.escape(rule.lower())}(?:_|$)", name) is not None


def _one_test(rule: str, test: str, source: TestSource) -> Sequence[str]:
    module, _, name = test.rpartition(".")
    body = source(module)
    if body is None or not re.search(rf"def {re.escape(name)}\(", body):
        return [f"unknown-test: {rule} names {test}, which is not there"]
    if not names_id(test, rule):
        return [f"test-without-id: {test} does not name the rule {rule}"]
    return []


def _test_findings(entry: Row, source: TestSource) -> Sequence[str]:
    if not entry.tests:
        return [f"unknown-test: {entry.id} lists no test"]
    found: list[str] = []
    for test in entry.tests:
        found.extend(_one_test(entry.id, test, source))
    return found


def _entry_findings(
    entry: Row, known: FunctionKnown, source: TestSource
) -> Sequence[str]:
    found: list[str] = []
    if entry.kind not in KINDS:
        found.append(f"unknown-kind: {entry.id} has kind {entry.kind!r}")
    if entry.kind in CHECKED:
        if not known(entry.function):
            found.append(
                f"unknown-function: {entry.id} names {entry.function}, which is not"
                " there"
            )
        found.extend(_test_findings(entry, source))
    return found


def findings(
    rows: Sequence[Row], known: FunctionKnown, source: TestSource
) -> Sequence[str]:
    """What the register gets wrong.

    Args:
        rows: the rows.
        known: whether a ``module.name`` function exists.
        source: the text of a test module by its name, None when there is none.

    Returns:
        A finding for each repeated id, unknown kind, unknown function, unknown
        test and test that does not name its rule.
    """
    counts = collections.Counter(entry.id for entry in rows)
    repeated = [f"duplicate-id: {each}" for each, n in counts.items() if n > 1]
    return [
        *repeated,
        *(found for entry in rows for found in _entry_findings(entry, known, source)),
    ]


def open_ids(rows: Sequence[Row]) -> Sequence[str]:
    """The ids of the rules not yet enforced.

    Args:
        rows: the rows.

    Returns:
        The ids of the rows of kind ``open``.
    """
    return [row.id for row in rows if row.kind == "open"]


def coverage_findings(rows: Sequence[Row], table: Sequence[str]) -> Sequence[str]:
    """What the register gets wrong against the coverage table (item 2).

    Args:
        rows: the rows.
        table: the ids of the coverage table.

    Returns:
        A finding if the rows of kind ``outside`` are not exactly ``OUTSIDE``, and
        for each id of the table with no row or a row neither enforced nor output.
    """
    held = {entry.id: entry for entry in rows}
    outside = sorted(entry.id for entry in rows if entry.kind == "outside")
    found = [f"outside-set: {outside}"] if outside != sorted(OUTSIDE) else []
    return [
        *found,
        *(f"table-id: {each} has no row" for each in table if each not in held),
        *(
            f"table-kind: {each} is {held[each].kind}"
            for each in table
            if each in held and each not in OUTSIDE and held[each].kind not in CHECKED
        ),
    ]

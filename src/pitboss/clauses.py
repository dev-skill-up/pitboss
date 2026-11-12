"""The rule lines of the owner's memory and the corrections of #444, each mapped.

The keyword is clauses.

``clauses.tsv`` has a row for every clause of the corpus: a bullet of ``MEMORY.md``, the
``description`` and the ``How to apply`` line of each topic file, and each numbered case
and each comment of ticket 444. A row names the ids of the register that cover it and a
word (``needle``) every one of them holds in its words or its tests, or says ``outside:
REASON``. ``findings`` refuses a clause of the corpus with no row, a row that names an
id the register lacks, a rule that is open (not enforced yet), one with no tests, a
needle none of the rule's words or tests holds, and an ``outside`` with no reason.
quire#1115: a rule was stated again and again because nothing listed which of its
clauses a test held.
"""

import dataclasses
import json
import pathlib
import re
from typing import Mapping, Sequence

from . import rules

OUTSIDE = "outside:"
MEMORY = "memory:"
TICKET = "ticket:444"
KEY = 48
FIELDS = 4
CASE = re.compile(r"^(\d+)\. ", re.MULTILINE)
Clause = tuple[str, str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Row:
    """A row of the table.

    Attributes:
        source: ``memory:FILE`` or ``ticket:444``.
        key: the clause's key in its source.
        maps: rule ids joined by commas, or ``outside: REASON``.
        needle: a word of the covering rules' words or tests, ``-`` for outside.
    """

    source: str
    key: str
    maps: str
    needle: str


def parse(text: str) -> Sequence[Row]:
    """The rows of the file.

    Args:
        text: the file; ``#`` lines and blank lines are skipped.

    Returns:
        The rows; one with a wrong number of fields is a ``ValueError``.
    """
    rows = [each.split("\t") for each in text.splitlines() if each.strip()]
    rows = [each for each in rows if not each[0].startswith("#")]
    for each in rows:
        if len(each) != FIELDS:
            raise ValueError(
                f"clauses.tsv: {each[0]} {each[1]!r} has {len(each)} fields"
            )
    return [Row(source=a, key=b, maps=c, needle=d) for a, b, c, d in rows]


def _memory_file(path: pathlib.Path) -> Sequence[Clause]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if path.name == "MEMORY.md":
        return [
            (MEMORY + path.name, re.sub(r"\s+", " ", each)[:KEY])
            for each in lines
            if each.startswith("- ")
        ]
    found = [
        ("description", each.startswith("description:"))
        for each in lines
        if each.startswith("description:")
    ]
    found += [
        ("how-to-apply", True) for each in lines if each.startswith("**How to apply:**")
    ]
    return [(MEMORY + path.name, name) for name, _ in found]


def memory(directory: pathlib.Path) -> Sequence[Clause]:
    """The clauses of a memory directory.

    Args:
        directory: the folder of ``MEMORY.md`` and the topic files.

    Returns:
        ``(source, key)`` for each bullet of ``MEMORY.md`` and the description and
        How to apply line of each topic file.
    """
    return [
        each for path in sorted(directory.glob("*.md")) for each in _memory_file(path)
    ]


def ticket(body: str, comments: str) -> Sequence[Clause]:
    """The corrections of ticket 444.

    Args:
        body: the ticket's body.
        comments: its comments, the JSON the API gives.

    Returns:
        ``(ticket:444, case N)`` for each numbered case after the ``### Cases``
        heading and ``(ticket:444, comment ID)`` for each comment.
    """
    cases = body.partition("### Cases")[2]
    found = [(TICKET, f"case {each.group(1)}") for each in CASE.finditer(cases)]
    return found + [(TICKET, f"comment {each['id']}") for each in json.loads(comments)]


def _covering(row: Row, register: Mapping[str, rules.Row]) -> Sequence[str]:
    where = f"{row.source} {row.key!r}"
    if row.maps.startswith(OUTSIDE):
        return (
            []
            if row.maps[len(OUTSIDE) :].strip()
            else [f"{where}: outside has no reason"]
        )
    found = []
    held = []
    for each in row.maps.split(","):
        rule = register.get(each)
        if rule is None:
            found.append(f"{where}: {each} is no rule of the register")
        elif rule.kind == "open":
            found.append(f"{where}: {each} is open, not enforced yet")
        elif rule.kind in rules.CHECKED and not rule.tests:
            found.append(f"{where}: {each} has no tests")
        else:
            held.append(" ".join([rule.words, *rule.tests]).lower())
    if held and not any(row.needle.lower() in each for each in held):
        found.append(
            f"{where}: no mapped rule holds {row.needle!r} in its words or tests"
        )
    return found


def findings(
    text: str, register: Sequence[rules.Row], corpus: Sequence[Clause]
) -> Sequence[str]:
    """What the table gets wrong.

    Args:
        text: ``clauses.tsv``.
        register: the rows of the register.
        corpus: the clauses of the sources, empty to check the table alone.

    Returns:
        A finding for a clause with no row, a row of a source in the corpus whose
        clause is gone, and each fault of ``_covering``.
    """
    rows = parse(text)
    by_id = {each.id: each for each in register}
    keys = {(each.source, each.key) for each in rows}
    present = {source for source, _ in corpus}
    found = [
        f"{s} {k!r}: no row in clauses.tsv" for s, k in corpus if (s, k) not in keys
    ]
    found += [
        f"{each.source} {each.key!r}: the clause is not in the corpus"
        for each in rows
        if each.source in present and (each.source, each.key) not in set(corpus)
    ]
    for each in rows:
        found += _covering(each, by_id)
    return found

"""The gate each task, step and action passes (keyword: action-gates, quire#1110).

quire#1110: a PR dropped from the merge queue was offered a re-arm of auto-merge
during a quiet period of the runner hold, because the action was derived by no
table that asked of each state change whether a gate covers it. ``actiongates.tsv``
has a row for every ``steps.Task``, ``steps.Step`` and ``actions.Action``: the gate
(``hold``, ``pressure`` or ``free`` with its reason), where it is made and the test
that shows it. ``findings`` is the check, run by a test, so a member added to the
code with no row, a row of no member, and a step the matrix lets make a gated
action while its own row is ``free`` all fail.
"""

import enum
from typing import Callable, Mapping, Sequence

from . import actions, steps, tablefile


class Gate(enum.Enum):
    """What a row's state change waits for (its word is the name in lower case).

    Attributes:
        HOLD: a runner hold.
        PRESSURE: runner pressure.
        FREE: nothing; the row says why.
    """

    HOLD = enum.auto()
    PRESSURE = enum.auto()
    FREE = enum.auto()


def gate_of(word: str) -> Gate | None:
    """The gate a row's word names.

    Args:
        word: the word.

    Returns:
        The gate, or None for a word that names none.
    """
    return Gate.__members__.get(word.upper()) if word.islower() else None


RUNNER_COST = ("PUSH", "MERGE", "UNDRAFT", "DISPATCH", "ARM")  # the gated actions
FIELDS = 4


def parse(table: str) -> Mapping[str, tuple[str, str, str]]:
    """The rows of the file.

    Args:
        table: the file; ``#`` lines and blank lines are skipped.

    Returns:
        ``(gate, where, test)`` by id; a row with a wrong number of fields is a
        ``ValueError``.
    """
    return {
        name: (gate, where, test)
        for name, gate, where, test in tablefile.rows(table, "actiongates.tsv", FIELDS)
    }


def members() -> Sequence[str]:
    """The ids the table must have.

    Returns:
        ``Task.X``, ``Step.X`` and ``Action.X`` for every member.
    """
    return [
        *(f"Task.{each.name}" for each in steps.Task),
        *(f"Step.{each.name}" for each in steps.Step),
        *(f"Action.{each.name}" for each in actions.Action),
    ]


def _row_findings(
    rows: Mapping[str, tuple[str, str, str]], exists: Callable[[str], bool]
) -> Sequence[str]:
    found = []
    for name, (word, where, test) in rows.items():
        gate = gate_of(word)
        if gate is None:
            known = ", ".join(each.name.lower() for each in Gate)
            found.append(f"{name}: the gate {word!r} is none of {known}")
        elif gate is Gate.FREE and not where.strip():
            found.append(f"{name}: a free row says why")
        elif gate is not Gate.FREE and not exists(test):
            found.append(f"{name}: the test {test!r} does not exist")
    return found


def _matrix_findings(
    rows: Mapping[str, tuple[str, str, str]], matrix: str
) -> Sequence[str]:
    grid = actions.parse(matrix)[1]
    return [
        f"{state} may make {action.lower()} but its gate is free"
        for state, cells in grid.items()
        for action in RUNNER_COST
        if cells.get(f"Action.{action}") == "y"
        and gate_of(rows.get(state, ("free",))[0]) is Gate.FREE
    ]


def findings(table: str, matrix: str, exists: Callable[[str], bool]) -> Sequence[str]:
    """What the table gets wrong.

    Args:
        table: the gate table.
        matrix: the text of ``actionmatrix.tsv``.
        exists: whether a named test exists.

    Returns:
        A finding for a member with no row, a row of no member, a gate that is
        not a ``Gate``, a ``hold`` or ``pressure`` row whose test does not
        exist, a ``free`` row with no reason, and a step the matrix allows a gated
        action at whose row is ``free``.
    """
    rows = parse(table)
    found = [f"{each} has no gate row" for each in members() if each not in rows]
    found += [
        f"{each} is no task, step or action" for each in rows if each not in members()
    ]
    return [*found, *_row_findings(rows, exists), *_matrix_findings(rows, matrix)]

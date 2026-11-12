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

from typing import Callable, Mapping, Sequence

from . import actions, steps

GATES = ("hold", "pressure", "free")
GATED = ("PUSH", "MERGE", "UNDRAFT", "DISPATCH", "ARM")  # the actions with runner cost
FIELDS = 4


def parse(text: str) -> Mapping[str, tuple[str, str, str]]:
    """The rows of the file.

    Args:
        text: the file; ``#`` lines and blank lines are skipped.

    Returns:
        ``(gate, where, test)`` by id; a row with a wrong number of fields is a
        ``ValueError``.
    """
    rows = [each.split("\t") for each in text.splitlines() if each.strip()]
    rows = [each for each in rows if not each[0].startswith("#")]
    for each in rows:
        if len(each) != FIELDS:
            raise ValueError(f"actiongates.tsv: {each[0]} has {len(each)} fields")
    return {name: (gate, where, test) for name, gate, where, test in rows}


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


def findings(text: str, matrix: str, exists: Callable[[str], bool]) -> Sequence[str]:
    """What the table gets wrong.

    Args:
        text: the gate table.
        matrix: the text of ``actionmatrix.tsv``.
        exists: whether a named test exists.

    Returns:
        A finding for a member with no row, a row of no member, a gate that is
        not one of ``GATES``, a ``hold`` or ``pressure`` row whose test does not
        exist, a ``free`` row with no reason, and a step the matrix allows a gated
        action at whose row is ``free``.
    """
    rows = parse(text)
    found = [f"{each} has no gate row" for each in members() if each not in rows]
    found += [
        f"{each} is no task, step or action" for each in rows if each not in members()
    ]
    for name, (gate, where, test) in rows.items():
        if gate not in GATES:
            found.append(f"{name}: the gate {gate!r} is none of {', '.join(GATES)}")
        elif gate == "free" and not where.strip():
            found.append(f"{name}: a free row says why")
        elif gate != "free" and not exists(test):
            found.append(f"{name}: the test {test!r} does not exist")
    grid = actions.parse(matrix)[1]
    for state, cells in grid.items():
        for action in GATED:
            if (
                cells.get(f"Action.{action}") == "y"
                and rows.get(state, ("free",))[0] == "free"
            ):
                found.append(f"{state} may make {action.lower()} but its gate is free")
    return found

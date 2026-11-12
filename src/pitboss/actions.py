"""The state-changing actions on GitHub, and the matrix that allows each (keyword: action-matrix).

Seen on promise#73: a merge made around a runner-pressure hold, with a raw ``gh``
call no pitboss command saw. Every action that changes a PR on GitHub is one of
``Action``, goes through ``pitboss act``, which asks ``actionmatrix.tsv`` whether
the PR's step allows it, refuses when not, and writes a ledger record; the sweep
names each GitHub event of these kinds that has no record (``unledgered``). The
columns of the matrix are the members of ``steps.Task`` and of ``Action``, its
rows the members of ``steps.Step`` and of ``Standing``.
"""

import enum
from typing import Mapping, Sequence

from . import steps

ALLOWED = "y"
REFUSED = "n"
EXEMPT = "# matrix-exempt:"
VERBS = ("merge", "undraft", "dispatch", "close", "label", "push", "rerun", "delete")


class Action(enum.Enum):
    """What changes a PR on GitHub.

    Attributes:
        PUSH: push commits to its branch.
        MERGE: merge it.
        UNDRAFT: mark it ready for review.
        DISPATCH: dispatch a workflow on its branch.
        CLOSE: close it.
        LABEL: put a label on it.
    """

    PUSH = "push"
    MERGE = "merge"
    UNDRAFT = "undraft"
    DISPATCH = "dispatch"
    CLOSE = "close"
    LABEL = "label"


class Standing(enum.Enum):
    """What else a PR can be besides its step (read by the sweep, not the flow).

    Attributes:
        PLAIN: nothing else.
        DUPLICATE: a second PR on a ticket another PR works (keyword: duplicate-pr).
    """

    PLAIN = "plain"
    DUPLICATE = "duplicate"


def rows() -> Sequence[str]:
    """The rows of the matrix.

    Returns:
        ``Step.X`` for each step and ``Standing.X`` for each standing.
    """
    return [f"Step.{each.name}" for each in steps.Step] + [
        f"Standing.{each.name}" for each in Standing
    ]


def columns() -> Sequence[str]:
    """The columns of the matrix.

    Returns:
        ``Task.X`` for each task and ``Action.X`` for each action.
    """
    return [f"Task.{each.name}" for each in steps.Task] + [
        f"Action.{each.name}" for each in Action
    ]


def parse(text: str) -> tuple[Sequence[str], Mapping[str, Mapping[str, str]], Mapping[str, str]]:
    """Read the matrix file.

    Args:
        text: the file: a header line ``state TAB column...``, a row for each
            state, ``# matrix-exempt: WORD: REASON`` lines, other ``#`` lines and
            blank lines skipped.

    Returns:
        The header's columns, the cells of each row by column, and the reason of
        each exempt word.
    """
    header: Sequence[str] = ()
    grid: dict[str, Mapping[str, str]] = {}
    exempt: dict[str, str] = {}
    for line in filter(str.strip, text.splitlines()):
        if line.startswith(EXEMPT):
            word, _, why = line[len(EXEMPT) :].strip().partition(":")
            exempt[word.strip()] = why.strip()
        elif line.startswith("#"):
            continue
        elif line.startswith("state\t"):
            header = line.split("\t")[1:]
        else:
            name, *cells = line.split("\t")
            grid[name] = dict(zip(header, cells))
    return header, grid, exempt


def _cells(
    header: Sequence[str], grid: Mapping[str, Mapping[str, str]]
) -> Sequence[str]:
    found = [f"{each} is no column of the matrix" for each in columns() if each not in header]
    found += [f"{each} is no member of steps or actions" for each in header if each not in columns()]
    found += [f"{each} has no row in actionmatrix.tsv" for each in rows() if each not in grid]
    found += [f"{each} is no state of the code" for each in grid if each not in rows()]
    for state, cells in grid.items():
        found += [
            f"{state} has no cell for {each}" for each in columns() if each not in cells
        ]
        found += [
            f"{state} {column} is {value!r}, not y or n"
            for column, value in cells.items()
            if value not in {ALLOWED, REFUSED}
        ]
    return found


def findings(
    text: str, wording: Sequence[str]
) -> Sequence[str]:
    """What the matrix gets wrong.

    Args:
        text: the matrix file.
        wording: the words of the rules of the register.

    Returns:
        A finding for each missing or surplus row, column or cell, a cell that is
        neither ``y`` nor ``n``, and each verb of an action that some rule's words
        use and that is neither an ``Action`` nor marked ``matrix-exempt``.
    """
    header, grid, exempt = parse(text)
    known = {each.value for each in Action} | set(exempt)
    found = list(_cells(header, grid))
    used = {
        verb
        for words in wording
        for verb in VERBS
        if verb in words.lower().replace("-", "")
    }
    found += [
        f"the register uses the action word {verb!r}: add it to Action or mark it"
        f" `{EXEMPT} {verb}: REASON`"
        for verb in sorted(used - known)
    ]
    return found


def cell(grid: Mapping[str, Mapping[str, str]], state: str, column: str) -> bool:
    """Whether the matrix allows a column in a state.

    Args:
        grid: the parsed rows.
        state: ``Step.X`` or ``Standing.X``.
        column: ``Task.X`` or ``Action.X``.

    Returns:
        True for ``y``.
    """
    return grid[state][column] == ALLOWED


def refusal(
    grid: Mapping[str, Mapping[str, str]],
    action: Action,
    step: steps.Next,
    standing: Standing,
) -> str:
    """Why an action is refused for a PR, empty when it is allowed.

    Args:
        grid: the parsed rows.
        action: the action.
        step: the PR's step.
        standing: the PR's standing.

    Returns:
        The reason: the step and the standing, and the steps that allow it.
    """
    column = f"Action.{action.name}"
    here = (f"Step.{step.step.name}", f"Standing.{standing.name}")
    if any(cell(grid, state, column) for state in here):
        return ""
    allowing = [state for state, cells in grid.items() if cells[column] == ALLOWED]
    return (
        f"{action.value} is refused: the PR is at {here[0]} ({standing.value}); it is"
        f" allowed at {', '.join(allowing) or 'no state'} (actionmatrix.tsv)"
    )


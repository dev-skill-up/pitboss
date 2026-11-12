"""The state-changing actions on GitHub and the matrix that allows each.

The keyword is action-matrix. Seen on promise#73: a merge made around a
runner-pressure hold, with a raw ``gh`` call no pitboss command saw. Every action
that changes a PR on GitHub is one of ``Action``, goes through ``pitboss act``,
which asks ``actionmatrix.tsv`` whether the PR's step allows it, refuses when not,
and writes a ledger record; the sweep
names each GitHub event of these kinds that has no record (``unledgered``). The
columns of the matrix are the members of ``steps.Task`` and of ``Action``, its
rows the members of ``steps.Step`` and of ``Standing``.
"""

import enum
from typing import Mapping, Sequence

from . import steps

CELLS: Mapping[str, bool] = {"y": True, "n": False}
EXEMPT = "# matrix-exempt:"
VERBS = ("merge", "undraft", "dispatch", "close", "label", "push", "rerun", "delete")


class Action(enum.Enum):
    """What changes a PR on GitHub.

    Attributes:
        PUSH: push commits to its branch.
        MERGE: merge it.
        ARM: arm auto-merge again (keyword: dropped-from-queue).
        UNDRAFT: mark it ready for review.
        DISPATCH: dispatch a workflow on its branch.
        CLOSE: close it.
        LABEL: put a label on it.
    """

    PUSH = enum.auto()
    MERGE = enum.auto()
    UNDRAFT = enum.auto()
    DISPATCH = enum.auto()
    CLOSE = enum.auto()
    LABEL = enum.auto()
    ARM = enum.auto()


class Standing(enum.Enum):
    """What else a PR can be besides its step (read by the sweep, not the flow).

    Attributes:
        PLAIN: nothing else.
        DUPLICATE: a second PR on a ticket another PR works (keyword: duplicate-pr).
    """

    PLAIN = enum.auto()
    DUPLICATE = enum.auto()


def word(action: Action) -> str:
    """The word of an action on the command line and in the ledger.

    Args:
        action: the action.

    Returns:
        Its name in lower case.
    """
    return action.name.lower()


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


def _exempt(line: str) -> tuple[str, str]:
    named, _, why = line[len(EXEMPT) :].strip().partition(":")
    return named.strip(), why.strip()


def parse(
    text: str,
) -> tuple[Sequence[str], Mapping[str, Mapping[str, str]], Mapping[str, str]]:
    """Read the matrix file.

    Args:
        text: the file: a header line ``state TAB column...``, a row for each
            state, ``# matrix-exempt: WORD: REASON`` lines, other ``#`` lines and
            blank lines skipped.

    Returns:
        The header's columns, the cells of each row by column, and the reason of
        each exempt word.
    """
    lines = list(filter(str.strip, text.splitlines()))
    exempt = dict(_exempt(each) for each in lines if each.startswith(EXEMPT))
    heads = [each.split("\t")[1:] for each in lines if each.startswith("state\t")]
    header = heads[0] if heads else []
    rows_ = [
        each.split("\t")
        for each in lines
        if not each.startswith("#") and not each.startswith("state\t")
    ]
    return header, {name: dict(zip(header, cells)) for name, *cells in rows_}, exempt


def _cells(
    header: Sequence[str], grid: Mapping[str, Mapping[str, str]]
) -> Sequence[str]:
    found = [
        f"{each} is no column of the matrix" for each in columns() if each not in header
    ]
    found += [
        f"{each} is no member of steps or actions"
        for each in header
        if each not in columns()
    ]
    found += [
        f"{each} has no row in actionmatrix.tsv" for each in rows() if each not in grid
    ]
    found += [f"{each} is no state of the code" for each in grid if each not in rows()]
    for state, cells in grid.items():
        found += [
            f"{state} has no cell for {each}" for each in columns() if each not in cells
        ]
        found += [
            f"{state} {column} is {value!r}, not y or n"
            for column, value in cells.items()
            if value not in CELLS
        ]
    return found


def findings(text: str, wording: Sequence[str]) -> Sequence[str]:
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
    known = {word(each) for each in Action} | set(exempt)
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
    return CELLS.get(grid[state][column], False)


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
    allowing = [
        state for state, cells in grid.items() if CELLS.get(cells[column], False)
    ]
    return (
        f"{word(action)} is refused: the PR is at {here[0]}"
        f" ({standing.name.lower()}); it is allowed at"
        f" {', '.join(allowing) or 'no state'} (actionmatrix.tsv)"
    )

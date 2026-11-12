"""Every step and task has a printed next step (keyword: step-matrix, quire#1115).

``stepmatrix.tsv`` has a row for each member of ``steps.Step`` and ``steps.Task``:
the member, what ``slots next`` and the sweep must print for it (``brief`` a ruling
brief, ``category`` a round the worker is briefed for, ``line`` a sweep line with a
marker, ``next`` a NEXT line, ``state`` the PR STATE text alone) and the reason when
that is ``state``. A new member with no row, a row with no member, and a step whose
text asks for an Opus ruling but is not ``brief`` are findings. The module reads the
enums and the text it is given; it prints nothing.
"""

import enum
from typing import Mapping, Sequence, Type

from . import steps

NEEDS = ("brief", "category", "line", "next", "state")
# keyword: plan-edited-brief (quire#1115): an edited Plan is cleared by a ruling
RULINGS = frozenset({steps.Step.OPUS_RULING, steps.Step.PLAN_EDITED})
ASKS_RULING = ("ask an Opus agent", "start an Opus agent")


def members(
    step: Type[enum.Enum] = steps.Step, task: Type[enum.Enum] = steps.Task
) -> Sequence[str]:
    """The names of the steps and tasks, as ``Step.X`` and ``Task.X``.

    Args:
        step: the enum of the steps.
        task: the enum of the tasks.

    Returns:
        Each member of both, in order.
    """
    return [f"Step.{each.name}" for each in step] + [
        f"Task.{each.name}" for each in task
    ]


def parse(text: str) -> Mapping[str, tuple[str, str]]:
    """The rows of a three-column file.

    Args:
        text: the file: ``name TAB word TAB rest`` on each line; ``#`` lines and
            blank lines are skipped.

    Returns:
        The word and the rest of each name.
    """
    parsed: dict[str, tuple[str, str]] = {}
    for line in filter(lambda each: each.strip() and each[0] != "#", text.splitlines()):
        name, need, *why = line.split("\t")
        parsed[name] = (need, "".join(why))
    return parsed


def _bad_row(name: str, row: tuple[str, str]) -> str:
    need, why = row
    if need not in NEEDS:
        return f"{name}: unknown need {need!r}"
    return (
        f"{name}: a state row names its reason" if need == "state" and not why else ""
    )


def _unbriefed(name: str, text: str, rows: Mapping[str, tuple[str, str]]) -> str:
    asks = any(ask in text for ask in ASKS_RULING)
    if asks and rows.get(name, ("", ""))[0] != "brief":
        return f"{name}: its text asks for an Opus ruling, so it needs a brief"
    return ""


def findings(
    rows: Mapping[str, tuple[str, str]],
    named: Sequence[str],
    texts: Mapping[str, str],
) -> Sequence[str]:
    """What is wrong with the rows.

    Args:
        rows: the parsed file.
        named: the members of the enums.
        texts: the PR STATE text of each member that has one.

    Returns:
        A finding for a member with no row, a row with no member, an unknown need,
        a ``state`` row with no reason and a step that asks for a ruling but is
        not ``brief``.
    """
    found = [
        f"{each} has no row in stepmatrix.tsv" for each in named if each not in rows
    ]
    found += [f"{each} is no member of steps" for each in rows if each not in named]
    found += [_bad_row(each, row) for each, row in rows.items()]
    found += [_unbriefed(each, text, rows) for each, text in texts.items()]
    return [each for each in found if each]

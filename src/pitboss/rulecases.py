"""Rulings as cases: a conflict between rulings is a red suite (pitboss#444).

Keyword: ruling-cases. A ruling of the owner that changes what pitboss lets
through is one case: an id, the date, a world, an action and the verdict he
ruled (GO or STOP). ``add`` accepts a new case only when some encoding of the
rows passes it together with every older case, and otherwise refuses, naming the
older cases it cannot keep: one question to the owner, with the two worlds as the
example. ``diff_findings`` refuses a change of the cases that drops a case or
flips its verdict with no record of the ruling that wins over it.
"""

import dataclasses
from typing import Callable, Mapping, Sequence

Encoding = Callable[[str, Mapping[str, object]], str]


class Refused(Exception):
    """No encoding passes the new case together with the old ones."""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """One ruling, as a world and the verdict ruled.

    Attributes:
        name: the ruling's id.
        date: when it was ruled.
        world: what the verdict reads.
        action: the action.
        expect: GO or STOP.
    """

    name: str
    date: str
    world: Mapping[str, object]
    action: str
    expect: str


def failures(cases: Sequence[Case], encoding: Encoding) -> Sequence[str]:
    """The cases an encoding does not pass.

    Args:
        cases: the cases.
        encoding: the verdict as some rows make it.

    Returns:
        Their ids.
    """
    return [
        each.name for each in cases if encoding(each.action, each.world) != each.expect
    ]


def add(cases: Sequence[Case], new: Case, encodings: Mapping[str, Encoding]) -> str:
    """Accept a new case when some encoding passes it with every older one.

    Args:
        cases: the older cases.
        new: the new one.
        encodings: the candidate encodings, by name.

    Returns:
        The name of the first encoding that passes every case.

    Raises:
        Refused: no encoding does; the message names the older cases lost.
    """
    every = [*cases, new]
    for name, encoding in encodings.items():
        if not failures(every, encoding):
            return name
    keeping = [
        encoding for encoding in encodings.values() if not failures([new], encoding)
    ]
    lost = sorted(
        {each for encoding in keeping for each in failures(cases, encoding)}
    ) or ["every encoding (none passes it)"]
    raise Refused(
        f"ruling {new.name} ({new.date}) cannot hold together with {', '.join(lost)}: no"
        " encoding passes both. One question to the owner, with the two worlds as the"
        " example; his answer is recorded as `wins`."
    )


def diff_findings(
    old: Sequence[Case], new: Sequence[Case], wins: Mapping[str, str]
) -> Sequence[str]:
    """What a change of the cases drops or flips with no ruling recorded.

    Args:
        old: the cases before.
        new: the cases after.
        wins: each dropped or flipped case and the ruling that wins over it.

    Returns:
        A line for each such case.
    """
    after = {each.name: each for each in new}
    found = []
    for case in old:
        if case.name in wins:
            if wins[case.name] not in after:
                found.append(
                    f"case {case.name}: the ruling named as winning, {wins[case.name]}, is not in the case file"
                )
        elif case.name not in after:
            found.append(
                f"case {case.name} is removed and no ruling is recorded as winning over it"
            )
        elif after[case.name].expect != case.expect:
            found.append(
                f"case {case.name} changes from {case.expect} to {after[case.name].expect} with no ruling recorded"
            )
    return found

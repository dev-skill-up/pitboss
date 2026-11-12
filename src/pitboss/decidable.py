"""Which output and outside rules a program could decide (keyword: decidable).

Seen on rp#683: a rule of the register ("no scratch paths in Plans") was kept by
the reviewer alone, and ``plan-check`` passed what it forbids. ``decidable.tsv``
has a row for every rule of kind ``output`` or ``outside``: ``checked`` with the
function that detects a break, or ``outside`` with the reason no program given
what pitboss reads can decide it. A rule with no row, a row of another kind of
rule, a ``checked`` row whose function is not the register's, and an ``outside``
row with a short reason are findings. The module reads no file.
"""

import enum
from typing import Mapping, Sequence

from . import rules, stepmatrix


class Verdict(enum.Enum):
    """What a rule's row says.

    Attributes:
        CHECKED: a function detects a break.
        OUTSIDE: no program given what pitboss reads can decide.
    """

    CHECKED = enum.auto()
    OUTSIDE = enum.auto()


KINDS = ("output", "outside")
MIN_REASON = 30


parse = stepmatrix.parse


def _row(rule: rules.Row, held: Mapping[str, tuple[str, str]]) -> str:
    if rule.id not in held:
        return f"decidable: {rule.id} ({rule.kind}) has no row in decidable.tsv"
    verdict, detail = held[rule.id]
    if verdict not in {each.name.lower() for each in Verdict}:
        return f"decidable: {rule.id} has the verdict {verdict!r}"
    if verdict == Verdict.CHECKED.name.lower() and detail != rule.function:
        return f"decidable: {rule.id} is checked by {detail}, not {rule.function}"
    if verdict == Verdict.OUTSIDE.name.lower() and len(detail) < MIN_REASON:
        return f"decidable: {rule.id} is outside with no reason of its own"
    return ""


def findings(
    register: Sequence[rules.Row], held: Mapping[str, tuple[str, str]]
) -> Sequence[str]:
    """What the file gets wrong about the register.

    Args:
        register: the rows of ``rules.tsv``.
        held: the parsed ``decidable.tsv``.

    Returns:
        A finding for each rule of kind output or outside with no valid row, and
        for each row of a rule that is neither.
    """
    wanted = [each for each in register if each.kind in KINDS]
    names = {each.id for each in wanted}
    found = [_row(each, held) for each in wanted]
    found += [
        f"decidable: {each} is no output or outside rule of the register"
        for each in held
        if each not in names
    ]
    return [each for each in found if each]

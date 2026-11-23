"""An impossibility cites the rulings it rests on, in their exact words (pitboss#487).

Moshe, 2026-11-22 02:09Z: "impossibility should either be conflict between ruling
and reality or two or more rulings, and they should cite exact words." A filing
for ``pitboss impossible`` therefore holds a ``Cites: "<words>"`` line for each
ruling it rests on (one against reality, two or more against each other), and
each quote is found in the register of the owner's rules or in the PR's Opus
ruling. The module reads nothing: the register's words and the PR's rulings are
given.
"""

import re
from typing import Sequence

CITE = re.compile(r'(?m)^Cites:[ \t]*"([^"\n]+)"[ \t]*$')
NONE = (
    'the hand-back cites no ruling: a `Cites: "<exact words>"` line for the ruling'
    " that conflicts with reality, or for each of two or more rulings that conflict"
)
UNFOUND = (
    "the cited words are in no ruling of the register or of the PR's Opus ruling:"
    " {words!r}"
)


def _squeezed(words: str) -> str:
    return re.sub(r"\s+", " ", words)


def refusal(handback: str, register: Sequence[str], rulings: Sequence[str]) -> str:
    """Say why a filing's citations do not support an impossibility.

    Args:
        handback: the filing's text.
        register: the words of each rule of the register.
        rulings: the text of each Opus ruling of the PR.

    Returns:
        The reason; empty when it cites at least one ruling and every quote is,
        exactly, in a rule of the register or in an Opus ruling.
    """
    cited = CITE.findall(handback)
    known = [_squeezed(each) for each in [*register, *rulings]]
    unfound = [each for each in cited if not any(_squeezed(each) in k for k in known)]
    if not cited:
        return NONE
    return UNFOUND.format(words=unfound[0]) if unfound else ""

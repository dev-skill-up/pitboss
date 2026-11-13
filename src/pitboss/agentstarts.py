"""Which decisions start an agent, and so get a brief (keyword: one-path).

A worker, a reviewer or an Opus agent takes a decision; a pull request at no round
(a refused Plan check, sent back by the worker that pushed it) starts none.
"""

from typing import Mapping

from . import answer, work, world

BRIEFED = frozenset({answer.Actor.WORKER, answer.Actor.REVIEWER, answer.Actor.RULING})


def starts(decided: answer.Decision, records: Mapping[str, world.Record]) -> bool:
    """Whether an agent starts for a decision.

    Args:
        decided: the decision.
        records: the record of each decided item.

    Returns:
        True for a decision of an actor that is briefed, but a pull request of no
        round that is not an Opus ruling.
    """
    if decided.actor not in BRIEFED:
        return False
    found = records[decided.item]
    if isinstance(found, world.PullRecord) and decided.actor is not answer.Actor.RULING:
        return work.category_of(found.facts) is not None
    return True

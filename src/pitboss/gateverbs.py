"""What ``act`` merge, arm, undraft and override look up in a decision (keyword: gate).

The one-path plan, P8: the verb runs only when the item's decision is its own, and
an override lifts only the stop the decision answers. The decision itself is made
by ``gate`` and ``decide``; nothing here reads or decides.
"""

import enum
from typing import Mapping, assert_never

from . import answer, project


class Verb(enum.Enum):
    """An act verb that runs only when the item's decision is its own.

    Attributes:
        MERGE: ``act merge``.
        ARM: ``act arm``.
        UNDRAFT: ``act undraft``.
        OVERRIDE: ``act override``, which lifts the stop the decision answers.
        DISPATCH_NEXT: ``act dispatch-next``, the head of the order.
    """

    MERGE = enum.auto()
    ARM = enum.auto()
    UNDRAFT = enum.auto()
    OVERRIDE = enum.auto()
    DISPATCH_NEXT = enum.auto()


Standing = answer.Standing


CARRIED: Mapping[Verb, answer.Carried] = {  # the step each gated verb carries out
    Verb.MERGE: answer.Carried.MERGE,
    Verb.ARM: answer.Carried.MERGE,
    Verb.UNDRAFT: answer.Carried.UNDRAFT,
}


def lookup(decided: answer.Decided, verb: Verb, item: str) -> Standing:
    """The decision that stands for a verb on an item (P8): act's one lookup.

    Args:
        decided: the decisions of the world the verb read.
        verb: the verb.
        item: the item it names (empty for ``dispatch-next`` of any).

    Returns:
        The item's decision for a verb on an item, the head of the order when the
        item has none; the head of the order for ``dispatch-next``.
    """
    match verb:
        case Verb.MERGE | Verb.ARM | Verb.UNDRAFT | Verb.OVERRIDE:
            return decided.by_item.get(item) or project.dispatch_next(decided)
        case Verb.DISPATCH_NEXT:
            return project.dispatch_next(decided)
        case _:  # pragma: no cover
            assert_never(verb)


def overridable(found: Standing, item: str, line: str) -> bool:
    """Whether ``act override`` may lift a stop: the item's decision answers it.

    Args:
        found: the decision that stands (``lookup``).
        item: the item the override names.
        line: the stop line.

    Returns:
        True when the decision is the route of that stop and the route is one an
        override lifts.
    """
    if not isinstance(found, answer.Decision) or found.item != item:
        return False
    return line != "" and found.lifts == line


def allows(verb: Verb, found: Standing, item: str) -> bool:
    """Whether an act verb runs: the decision that stands is the verb's own.

    Args:
        verb: ``MERGE``, ``ARM`` or ``UNDRAFT``.
        found: the decision that stands (``lookup``).
        item: the item the verb names.

    Returns:
        True when it is the item's decision and the step the verb carries out.
    """
    if not isinstance(found, answer.Decision) or found.item != item:
        return False
    wanted = CARRIED.get(verb, answer.Carried.NOTHING)
    return wanted is not answer.Carried.NOTHING and found.carried is wanted

"""What ``act`` merge, arm, undraft and override look up in a decision (keyword: gate).

The one-path plan, P8: the verb runs only when the item's decision is its own, and
an override lifts only the stop the decision answers. The decision itself is made
by ``gate`` and ``decide``; nothing here reads or decides.
"""

import enum
from typing import AbstractSet, Mapping, assert_never

from . import answer, project, steps, stepwords

UNREAD_SAID = "read the PR on GitHub and file what it answered"
TRIAGE = "triage the red: `act dispatch-next`"
KEPT_SAID = frozenset({UNREAD_SAID, TRIAGE})  # the routes no override lifts


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


MERGE_WORDS = frozenset({stepwords.TEXTS[steps.Step.MERGE], stepwords.ENQUEUE})
VERB_WORDS: Mapping[Verb, AbstractSet[str]] = {
    Verb.MERGE: MERGE_WORDS,
    Verb.ARM: MERGE_WORDS,
    Verb.UNDRAFT: {stepwords.TEXTS[steps.Step.UNDRAFT]},
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


def verb_of(stop_line: str, said: str) -> str:
    """The verb of a stopped PR's decision: what to do, and the stop it answers.

    Args:
        stop_line: the first stop's line.
        said: what the actor does.

    Returns:
        The verb (an override names the stop line in it).
    """
    return f"{said} ({stop_line})"


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
    said = found.verb.removesuffix(f" ({line})")
    return said != found.verb and said not in KEPT_SAID


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
    return found.verb in VERB_WORDS.get(verb, frozenset())

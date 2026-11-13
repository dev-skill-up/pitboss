"""The projections: one function for each question asked of the decisions (one-path).

Each takes the one ``decide.Decisions`` of a command and returns the type its
renderer takes, so two commands that ask one question print the value of one pure
function of one world.
"""

import dataclasses

from . import decide


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class ItemDecided:
    """The item asked about has a decision.

    Attributes:
        decision: its decision.
    """

    decision: decide.Decision


ItemAnswer = ItemDecided | decide.Work | decide.NotEnoughWork


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Dispatch:
    """The one next piece of work to dispatch.

    Attributes:
        decision: the head of the order.
    """

    decision: decide.Decision


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NotFirst:
    """The item the dispatch names is not the head of the order.

    Attributes:
        head: the head of the order.
        named: the item the dispatch named.
    """

    head: decide.Decision
    named: str


DispatchAnswer = Dispatch | NotFirst | decide.NotEnoughWork


def what_next(decisions: decide.Decisions) -> decide.Answer:
    """What is next: the question of ``next``, ``slots next`` and ``free-check``.

    Args:
        decisions: the command's decisions.

    Returns:
        The answer.
    """
    return decisions.answer


def item_next(decisions: decide.Decisions, reference: str) -> ItemAnswer:
    """What is next for one item: ``next <item>`` and ``slots next <item>``.

    Args:
        decisions: the command's decisions.
        reference: the item, ``owner/name#number``.

    Returns:
        Its decision when it has one, else the answer of the list, with nothing
        about the item.
    """
    found = decisions.by_item.get(reference)
    if found is not None:
        return ItemDecided(decision=found)
    return decisions.answer


def dispatch_next(decisions: decide.Decisions, named: str) -> DispatchAnswer:
    """The one next piece of work: ``act dispatch-next``, the head of the order.

    Args:
        decisions: the command's decisions.
        named: the item the caller means, empty for any.

    Returns:
        The head of the order, or that the named item is not it.
    """
    match decisions.answer:
        case decide.Work():
            head = decisions.answer.first
            if named and named != head.item:
                return NotFirst(head=head, named=named)
            return Dispatch(decision=head)
        case decide.NotEnoughWork():
            return decisions.answer

"""The renderers: each takes one projection's type and gives the lines (one-path).

A renderer decides nothing: it says the value it is given.
"""

from typing import Sequence

from . import decide, project

NOT_ENOUGH_WORK = (
    "NOT ENOUGH WORK: no open pull request and no ticket of the priority labels can"
    " be started now"
)


def decision_line(decision: decide.Decision) -> str:
    """One decision in a line.

    Args:
        decision: the decision.

    Returns:
        ``ACTOR: owner/name#N: what to do``.
    """
    return f"{decision.actor.value}: {decision.item}: {decision.verb}"


def answer(given: decide.Answer) -> Sequence[str]:
    """The lines of what is next.

    Args:
        given: the answer.

    Returns:
        ``NEXT n of m`` for each decision, first to take first, and the free
        slots; or the one ``NOT ENOUGH WORK`` line.
    """
    match given:
        case decide.Work():
            every = [given.first, *given.rest]
            total = len(every)
            listed = [
                f"NEXT {rank} of {total}. {decision_line(each)} ({each.title})"
                for rank, each in enumerate(every, start=1)
            ]
            return [*listed, f"SLOTS FREE: {given.free}"]
        case decide.NotEnoughWork():
            return [NOT_ENOUGH_WORK]


def item(given: project.ItemAnswer) -> Sequence[str]:
    """The lines of what is next for one item.

    Args:
        given: the item's decision, or the answer of the list.

    Returns:
        The decision's line, or the lines of the list.
    """
    match given:
        case project.ItemDecided():
            return [decision_line(given.decision)]
        case decide.Work() | decide.NotEnoughWork():
            return answer(given)


def dispatch(given: project.DispatchAnswer) -> Sequence[str]:
    """The lines of the one next piece of work.

    Args:
        given: the head of the order, or why the named item is not it.

    Returns:
        The item's reference; or the line that refuses.
    """
    match given:
        case project.Dispatch():
            return [given.decision.item]
        case project.NotFirst():
            return [f"the next in the order is {given.head.item}, not {given.named}"]
        case decide.NotEnoughWork():
            return [NOT_ENOUGH_WORK]


def first(given: decide.Answer) -> str:
    """The first decision of what is next, in a line.

    Args:
        given: the answer.

    Returns:
        The first decision's line, or the ``NOT ENOUGH WORK`` line.
    """
    match given:
        case decide.Work():
            return decision_line(given.first)
        case decide.NotEnoughWork():
            return NOT_ENOUGH_WORK

"""The renderers: each takes one projection's type and gives the lines (one-path).

A renderer decides nothing: it says the value it is given.
"""

from typing import Sequence

from . import answer, project

NOT_ENOUGH_WORK = (
    "NOT ENOUGH WORK: no open pull request and no ticket of the priority labels can"
    " be started now"
)


def decision_line(decision: answer.Decision) -> str:
    """One decision in a line.

    Args:
        decision: the decision.

    Returns:
        ``ACTOR: owner/name#N: what to do``.
    """
    return f"{decision.actor.name}: {decision.item}: {decision.verb}"


def every(given: answer.Work) -> Sequence[answer.Decision]:
    """The decisions of work, first to take first.

    Args:
        given: the work.

    Returns:
        The first decision, then the others.
    """
    return [given.first, *given.rest]


def answer_lines(given: answer.Answer) -> Sequence[str]:
    """The lines of what is next.

    Args:
        given: the answer.

    Returns:
        ``NEXT n of m`` for each decision, first to take first, and the free
        slots; or the one ``NOT ENOUGH WORK`` line.
    """
    match given:
        case answer.Work():
            listed = every(given)
            total = len(listed)
            lines = [
                f"NEXT {rank} of {total}. {decision_line(each)} ({each.title})"
                for rank, each in enumerate(listed, start=1)
            ]
            return [*lines, f"SLOTS FREE: {given.free}"]
        case answer.NotEnoughWork():
            return [NOT_ENOUGH_WORK]


def item(given: project.ItemAnswer) -> Sequence[str]:
    """The lines of what is next for one item.

    Args:
        given: the item's decision, or the answer of the list.

    Returns:
        The decision's line, or the lines of the list.
    """
    match given:
        case answer.Decision():
            return [decision_line(given)]
        case answer.Work() | answer.NotEnoughWork():
            return answer_lines(given)


def dispatch(given: answer.DispatchAnswer) -> Sequence[str]:
    """The lines of the one next piece of work.

    Args:
        given: the head of the order, or why the named item is not it.

    Returns:
        The item's reference; or the line that refuses.
    """
    match given:
        case answer.Decision():
            return [given.item]
        case answer.NotFirst():
            return [f"the next in the order is {given.head.item}, not {given.named}"]
        case answer.NotEnoughWork():
            return [NOT_ENOUGH_WORK]


def first(given: answer.Answer) -> str:
    """The first decision of what is next, in a line.

    Args:
        given: the answer.

    Returns:
        The first decision's line, or the ``NOT ENOUGH WORK`` line.
    """
    match given:
        case answer.Work():
            return decision_line(given.first)
        case answer.NotEnoughWork():
            return NOT_ENOUGH_WORK

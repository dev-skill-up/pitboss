"""The projections: one function for each question asked of the decisions (one-path).

Each takes the one ``answer.Decided`` of a command and returns the type its
renderer takes, so two commands that ask one question print the value of one pure
function of one world.
"""

from . import answer

ItemAnswer = answer.Decision | answer.Work | answer.NotEnoughWork
DispatchAnswer = answer.DispatchAnswer


def what_next(decided: answer.Decided) -> answer.Answer:
    """What is next: the question of ``next``, ``slots next`` and ``free-check``.

    Args:
        decided: the command's decisions.

    Returns:
        The answer.
    """
    return decided.answer


def item_next(decided: answer.Decided, reference: str) -> ItemAnswer:
    """What is next for one item: ``next <item>`` and ``slots next <item>``.

    Args:
        decided: the command's decisions.
        reference: the item, ``owner/name#number``.

    Returns:
        Its decision when it has one, else the answer of the list, with nothing
        about the item.
    """
    return decided.by_item.get(reference, decided.answer)


def dispatch_next(decided: answer.Decided, named: str) -> DispatchAnswer:
    """The one next piece of work: ``act dispatch-next``, the head of the order.

    Args:
        decided: the command's decisions.
        named: the item the caller means, empty for any.

    Returns:
        The head of the order, or that the named item is not it.
    """
    given = decided.answer
    match given:
        case answer.Work() if named and named != given.first.item:
            return answer.NotFirst(head=given.first, named=named)
        case answer.Work():
            return given.first
        case answer.NotEnoughWork():
            return given

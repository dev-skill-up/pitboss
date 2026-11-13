"""What an emptied slot takes next (keyword: one-path, ``slots free``).

It takes the first decision of the one answer that starts an agent its model
may take (at or above the item's floor, and not a model that failed the item),
as the suggestions place a decision in a slot; with none, the answer's first.
"""

from typing import Callable

from . import agentstarts, answer, config, decide, ledger, project, render
from . import suggest, work, world

Pick = Callable[[world.Record], suggest.Pick | None]


def _fits(
    judgement: decide.Judgement,
    book: ledger.Ledger,
    wanted: tuple[config.Slots, str, Pick],
    each: answer.Decision,
) -> bool:
    slots, model, pick = wanted
    taken = pick(judgement.records[each.item])
    starts = agentstarts.starts(each, judgement.records)
    if not starts or taken is None or taken.item is None:
        return False
    smallest = work.smallest_model(taken.item, slots, book.failed)
    return (
        smallest is not None
        and model in slots.models
        and model not in book.failed.get(each.item, ())
        and slots.models.index(smallest) <= slots.models.index(model)
    )


def line(
    read: tuple[decide.Judgement, ledger.Ledger],
    slots: config.Slots,
    name: str,
    pick: Pick,
) -> str:
    """What an emptied slot takes next.

    Args:
        read: the decisions of the command's one read, with their records, and
            the ledger the read gave.
        slots: the slot configuration.
        name: the slot.
        pick: what a slot takes for a record (``onepath.pick``).

    Returns:
        ``SLOT <name> NEXT: <the decision>``.
    """
    judgement, book = read
    given = project.what_next(judgement.decided)
    emptied = ledger.find(book, name)
    model = emptied.model if isinstance(emptied, ledger.Slot) else ""
    decisions = render.every(given) if isinstance(given, answer.Work) else []
    wanted = (slots, model, pick)
    fitting = [each for each in decisions if _fits(judgement, book, wanted, each)]
    said = render.decision_line(fitting[0]) if fitting else render.first(given)
    return f"SLOT {name} NEXT: {said}"

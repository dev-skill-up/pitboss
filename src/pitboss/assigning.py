"""Which empty slot takes which item.

Moved out of ``work`` to keep that module within its length limit (pitboss#388).
"""

from typing import Sequence

from . import config, ledger, work


def assign(
    items: Sequence[work.Item], book: ledger.Ledger, slots: config.Slots
) -> Sequence[work.Assignment]:
    """Give each empty slot, smallest model first, the first item it may take.

    Args:
        items: the ordered items.
        book: the ledger.
        slots: the slot configuration.

    Returns:
        Each empty slot with its item, or None when nothing fits.
    """
    rank = {model: index for index, model in enumerate(slots.models)}
    left = [
        (item, rank[model])
        for item in items
        if (model := work.smallest_model(item, slots, book.failed)) is not None
    ]
    found: list[work.Assignment] = []
    empty = [each for each in book.slots if not each.agent]
    for empty_slot in sorted(empty, key=lambda each: rank.get(each.model, len(rank))):
        size = rank.get(empty_slot.model, -1)
        index = next((at for at, pair in enumerate(left) if pair[1] <= size), None)
        found.append((empty_slot, None if index is None else left.pop(index)[0]))
    return found

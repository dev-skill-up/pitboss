"""A worker's decision on an item, as the fake hub's world gives it (P8, keyword: gate).

No act verb carries a worker's decision out, so ``act merge``, ``arm`` and
``undraft`` refuse it by its ``carried``.
"""

from .. import answer


def worker(item: str) -> answer.Decision:
    """A worker's decision on an item, which no act verb carries out.

    Args:
        item: the item.

    Returns:
        The decision.
    """
    return answer.Decision(
        actor=answer.Actor.WORKER,
        verb="",
        item=item,
        title="",
        carried=answer.Carried.NOTHING,
        lifts="",
    )

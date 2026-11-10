"""Where an item stood in the last full ``slots next`` (keyword: place-cache).

The place of one item in the order needs the whole order, which is what
``slots next TICKET`` no longer reads. The full ``slots next`` keeps the numbers
of its ``NEXT`` lines, and the one-item form says the place from them, and says
that it does.
"""

import pathlib
from typing import Mapping, Sequence

from . import nextfound, slotcache, slotheld
from .markers import Marker

PART = "order"
RULING = f"{Marker.NEXT.text} ruling, owed before every {Marker.NEXT.text} line"


def _path(found: nextfound.Found) -> pathlib.Path:
    return slotcache.path_of(found.settings.slots.ledger)


def record(
    found: nextfound.Found, queued: Sequence[str], first: int, complete: bool
) -> None:
    """Keep the order a full ``slots next`` printed.

    Args:
        found: the context.
        queued: the items of the ``NEXT`` lines, in order.
        first: the number of the first of them.
        complete: whether the list holds every queued item.
    """
    path = _path(found)
    kept = {
        "at": found.now.isoformat(),
        "numbers": {each: first + at for at, each in enumerate(queued)},
        "last": first + len(queued) - 1,
        "complete": complete,
    }
    slotcache.write(path, {**slotcache.read(path), PART: kept})


def _number(kept: Mapping[str, object], reference: str) -> int | None:
    numbers = kept.get("numbers")
    found = numbers.get(reference) if isinstance(numbers, dict) else None
    return found if isinstance(found, int) else None


def line(found: nextfound.Found, reference: str) -> str:
    """The first line of the brief of one item: where it stood, and since when.

    Args:
        found: the context.
        reference: the item.

    Returns:
        ``NEXT 24 of 30, out of order, 22 ahead of it`` as the last full
        ``slots next`` numbered it, then why that may be old; or that no list
        has the item.
    """
    marker = Marker.NEXT.text
    kept = slotcache.read(_path(found)).get(PART)
    if not isinstance(kept, dict):
        return f"{marker} place unknown: no full slots next has been run here yet"
    when = f"the full slots next of {kept.get('at')}"
    number = _number(kept, reference)
    if number is None:
        return f"{marker} place unknown: {reference} was not in {when}"
    ahead = number - (slotheld.LEAD + 1)
    order = f"out of order, {ahead} ahead of it" if ahead else "first in the order"
    more = "" if kept.get("complete") else "at least "
    return (
        f"{marker} {number} of {more}{kept.get('last')}, {order} (place from {when}:"
        " run slots next for today's)"
    )

"""The place of each item the walk examines (plan 6.3, P10; keyword: dependency).

A blocker an examined item names takes the better of its own place and the
places of the items that named it; ``places`` is the one function that says so,
and its only inputs are the listing rows and the blocker names of the items
examined so far. An item examined later has a later place, so nothing the walk
reads after the stop can move an item into or within the part it read.
"""

from typing import Mapping, Sequence

from . import listed

# each examined item, in the order examined, and the blockers it names
Named = Sequence[tuple[str, Sequence[str]]]


def places(rows: Sequence[listed.Listed], named: Named) -> Mapping[str, int]:
    """The place of each listing row, examined item and blocker named so far.

    Args:
        rows: the listing rows, in the order of the walk.
        named: each item examined so far, in order, with the blockers it names.

    Returns:
        Each place: a row's is its index; an examined item no row has comes after
        every row, in the order examined; a blocker's is the least of its own and
        its namers' places.
    """
    found = {row.reference: at for at, row in enumerate(rows)}
    after = len(rows)
    for at, (reference, blockers) in enumerate(named):
        mine = found.setdefault(reference, after + at)
        for each in blockers:
            found[each] = min(found.get(each, mine), mine)
    return found

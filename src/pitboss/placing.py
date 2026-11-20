"""The order the walk examines items in (plan 6.3, P10; keyword: dependency).

``order`` is the one function that says it, and the walk takes its next items from
it and from nothing else. Its only inputs are the references listed so far, in the
order of the listing, and the blocker names of the items examined so far. A blocker
an examined item names comes right after it, unless its own place is earlier: its
place is the least of its own and its namers' places. An item examined later only
adds names after itself, so nothing the walk reads after the stop can move an item
into or within the part it read.
"""

from typing import Sequence

# each examined item, in the order examined, and the blockers it names
Named = Sequence[tuple[str, Sequence[str]]]


def order(rows: Sequence[str], named: Named) -> Sequence[str]:
    """Each reference listed or named so far, in the order the walk examines them.

    Args:
        rows: the references listed so far, in the order of the listing.
        named: each item examined so far, in order, with the blockers it names.

    Returns:
        The references, each once: a row at its place, a blocker at the least of
        its own place and the place right after its first namer.
    """
    blockers_by = dict(named)
    placed: dict[str, None] = {}
    for reference in rows:
        todo = [reference]
        while todo:
            current = todo.pop()
            if current not in placed:
                placed[current] = None
                todo.extend(reversed(blockers_by.get(current, ())))
    return list(placed)

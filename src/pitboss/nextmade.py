"""The place line of the list that ``slots next`` prints (keyword: next-view).

Moved out of ``nextlist``: it needs nothing of ``suggest``, so it stays beside it.
"""

from typing import Sequence

from . import nextfound, placeline, slotheld, work

Found = nextfound.Found


def recorded(
    found: Found, ordered: work.Offered, shown: tuple[Sequence[work.Item], int]
) -> None:
    """Record the places the list shows, for the place line to read later.

    Args:
        found: the context.
        ordered: the ordered offer.
        shown: the items listed, and how many lines of ready PRs come first.
    """
    items, ready = shown
    queued = [each.reference for each in items]
    placeline.record(found, queued, slotheld.LEAD + 1 + ready, not ordered.unread)

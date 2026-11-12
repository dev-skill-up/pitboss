"""What the suggestions of ``slots next`` are made from (keyword: next-source).

Moved out of ``nextlist`` so that module stays under the line limit; it holds the
source of the picks (the open PRs, the volume, the largest directories) and the
``FIX ROUND WAITING`` lines that read the same PRs (keyword: fix-round-waiting).
"""

import dataclasses
from typing import Sequence

from . import (
    diskwatch,
    fixwait,
    ledger,
    machine,
    nextfound,
    pullmarks,
    pulls,
    suggest,
    work,
)

Found = nextfound.Found


def _big(found: Found, volume: diskwatch.Reading | None) -> Sequence[diskwatch.Big]:
    # keyword: disk-watch (pitboss#288): walked only when the suggestion is due
    if volume is None or not volume.crowded:
        return []
    return diskwatch.largest(machine.real(), found.clean.scratch)


def source(
    found: Found,
    opened: Sequence[pulls.Read],
    ordered: work.Offered,
    book: ledger.Ledger,
) -> suggest.Source:
    """What the suggestions are made from.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        ordered: the ordered offer.
        book: the slot ledger.

    Returns:
        The source, with the volume, the largest directories when the disk is
        crowded, and what holds the slots.
    """
    volume = diskwatch.read(found.args.usage, found.settings.project.workspace)
    return dataclasses.replace(
        suggest.sourced(
            found, pullmarks.awake(opened, ordered), ordered.items, book.failed
        ),
        volume=volume,
        big=_big(found, volume),
        occupancy=ordered.occupancy,
    )


def waiting(
    found: Found, made: suggest.Source, ordered: work.Offered, book: ledger.Ledger
) -> Sequence[str]:
    """The ``FIX ROUND WAITING`` lines (keyword: fix-round-waiting, case 38).

    Args:
        found: the context.
        made: the source of the suggestions.
        ordered: the ordered offer.
        book: the slot ledger.

    Returns:
        A line for each fix round that waits for its review with no agent on it.
    """
    held = {each.task for each in book.slots if each.agent}
    taken = held | set(ordered.occupancy.references)
    return fixwait.lines(made.facts, found.now, taken)

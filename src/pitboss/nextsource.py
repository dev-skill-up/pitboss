"""What the suggestions of ``slots next`` are made from (keyword: next-source).

Moved out of ``nextlist`` so that module stays under the line limit; it holds the
largest directories of a crowded disk and the PRs an agent works on (the
``FIX ROUND WAITING`` lines, keyword: fix-round-waiting); it does not import
``suggest``.
"""

from typing import AbstractSet, Sequence

from . import diskwatch, ledger, machine, nextfound, slotholder, work

Found = nextfound.Found


def big(found: Found, volume: diskwatch.Reading | None) -> Sequence[diskwatch.Big]:
    """The largest directories, walked only when the disk is crowded.

    Args:
        found: the context.
        volume: the volume reading, none when it was not read.

    Returns:
        The directories (keyword: disk-watch, pitboss#288).
    """
    if volume is None or not volume.crowded:
        return []
    return diskwatch.largest(machine.real(), found.clean.scratch)


def held(ordered: work.Offered, book: ledger.Ledger) -> AbstractSet[str]:
    """The PRs an agent works on (keyword: fix-round-waiting, case 38).

    Args:
        ordered: the ordered offer.
        book: the slot ledger.

    Returns:
        The tasks the slots hold and the references the offer counts as taken.
    """
    return slotholder.tasks(book) | set(ordered.occupancy.references)

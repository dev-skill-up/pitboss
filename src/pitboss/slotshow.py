"""The ledger as ``slots`` prints it: as written, and as the live agents make it."""

from typing import Sequence

from . import ledger, slotholding, slotreport


def written(running: Sequence[str] | None, book: ledger.Ledger) -> None:
    """Print the ledger as written.

    The PRs are not read here: only the live agents that hold no slot count.

    Args:
        running: the agents the session runs (``--running``), or None.
        book: the ledger.
    """
    taken = slotholding.written((), book, running)
    slotreport.print_ledger(book, taken)


def derived(running: Sequence[str] | None, book: ledger.Ledger) -> None:
    """Print the ledger the live agents make (pitboss#94), not the hand's rows.

    Args:
        running: the agents the session runs (``--running``), or None.
        book: the ledger.
    """
    rows = slotholding.derived(book, running)
    slotreport.print_ledger(rows, slotholding.occupy((), rows, running))

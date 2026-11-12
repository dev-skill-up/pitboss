"""Who holds a slot, for a refusal (case 36, keyword: slot-cap)."""

from typing import AbstractSet

from . import ledger


def agents(book: ledger.Ledger) -> AbstractSet[str]:
    """The agents the slots of a ledger record.

    Args:
        book: the ledger.

    Returns:
        Their names, the empty one of a free slot included.
    """
    return {each.agent for each in book.slots}


def tasks(book: ledger.Ledger) -> AbstractSet[str]:
    """The tasks the slots of a ledger hold for a running agent.

    Args:
        book: the ledger.

    Returns:
        Their references.
    """
    return {each.task for each in book.slots if each.agent}


def holder(slot: ledger.Slot) -> str:
    """The agent of a slot with its kind, task and the time it started.

    Args:
        slot: the slot.

    Returns:
        The agent's name, kind, task and since when.
    """
    return (
        f"{slot.agent} ({slot.kind or 'no kind'}, {slot.task or 'no task'},"
        f" since {slot.started or 'unknown'})"
    )

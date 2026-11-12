"""Who holds a slot, for a refusal (case 36, keyword: slot-cap)."""

from . import ledger


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

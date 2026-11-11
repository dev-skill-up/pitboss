"""The items that wait, for the task list (keyword: task-list, pitboss#471)."""

from typing import Sequence

from . import handedback, ledger, offering, pullmarks, pulls, slotholding, work
from .nextfound import Found


def queued_items(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> tuple[ledger.Ledger, Sequence[work.Item], Sequence[ledger.Slot]]:
    """The ledger as the live agents make it and the items waiting, in order.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger.

    Returns:
        The ledger, the ordered items and the slots whose worker handed back.
    """
    done = handedback.slots(found, opened, book)
    live = slotholding.live(
        found.args, book, handedback.release(found.args, (each.agent for each in done))
    )
    marks = pullmarks.pull_marks(found, opened)
    offer = offering.offered(found, offering.Look(opened=opened, marks=marks), live)
    return live, slotholding.counted(offer, opened, live, found.args).items, done

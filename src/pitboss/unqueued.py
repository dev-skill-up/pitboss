"""Why a ticket or PR is not in the order of ``slots next`` (keyword: unqueued).

The line ``UNKNOWN`` named only that nothing queues the item. It also says what
was read of it: its state, its labels, and the items that wait for it, so that a
blocker with no priority label of its own, or one that is closed, is told apart
from a ticket that was never read (pitboss#448).
"""

from typing import Sequence

from . import blockers, ghapi, work


def waiting(offer: work.Offered, reference: str) -> Sequence[str]:
    """The queued items that wait for a ticket.

    Args:
        offer: the queued work and the items kept back.
        reference: the ticket as ``owner/repo#N``.

    Returns:
        The references of the items that name it as a blocker, each once.
    """
    named = [each.reference for each in offer.blocked if reference in each.blockers]
    return list(dict.fromkeys([*offer.blocks.get(reference, ()), *named]))


def why(github: ghapi.GitHub, offer: work.Offered, reference: str) -> str:
    """What is known of an item that is not in the order.

    Args:
        github: the API.
        offer: the queued work and the items kept back.
        reference: the item as ``owner/repo#N``.

    Returns:
        Its state, its labels and the items it blocks, as one phrase.
    """
    ticket = blockers.read(github, reference)
    if ticket is None:
        return "it cannot be read"
    kind = "a PR" if ticket.pull else "a ticket"
    state = "open" if ticket.open else "closed"
    labels = ", ".join(sorted(ticket.labels)) or "none"
    blocks = ", ".join(waiting(offer, reference)) or "no item"
    return f"it is {kind}, state {state}, labels {labels}, blocks {blocks}"

"""The NOT THE HEAD line of ``next TICKET`` (keyword: not-the-head, pitboss#415).

A worker brief is printed from a listing read minutes earlier, and a p0 filed
since then should have taken the slot, so the brief is printed after the queue is
read again, and a ticket that is not the first startable item says so first.
"""

from typing import Sequence

from . import nextview, work
from .markers import Marker


def _label(item: work.Item, view: nextview.NextView) -> str:
    if item.category is work.Category.NEW_PR:
        return view.slots.priority_labels[item.priority]
    return work.CATEGORY_WORDS[item.category]


def line(view: nextview.NextView, ticket: str, given: str) -> Sequence[str]:
    """The line that says a ticket is not the head of ``slots next``.

    Args:
        view: the queue, read just now.
        ticket: the ticket whose brief is printed, as ``owner/repo#N``.
        given: the configuration as the command was given it.

    Returns:
        One line when the first startable item is another, else none.
    """
    found = nextview.startable(view)
    if not found or found[0].reference == ticket:
        return []
    head = found[0]
    ranks = [each.reference for each in found]
    rank = f"rank {ranks.index(ticket) + 1}" if ticket in ranks else "not in the order"
    return [
        f"{Marker.NOT_THE_HEAD.text}: {ticket} is {rank}; the head is"
        f" {head.reference} ({_label(head, view)}, opened {head.created_at[:10]});"
        f" its brief: pitboss slots next {head.reference} --config {given}"
    ]

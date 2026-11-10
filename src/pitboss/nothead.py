"""The NOT THE HEAD line of ``next TICKET`` (keyword: not-the-head, pitboss#415).

A worker brief is printed from a listing read minutes earlier, and a p0 filed
since then should have taken the slot, so the brief is printed after the queue is
read again, and a ticket that is not the first startable item says so first.
"""

from typing import Sequence

from . import work
from .markers import Marker


def _label(item: work.Item, labels: Sequence[str]) -> str:
    named = {work.Category.NEW_PR: labels[item.priority]}
    return named.get(item.category, work.CATEGORY_WORDS[item.category])


def line(
    found: Sequence[work.Item], labels: Sequence[str], ticket: str, given: str
) -> Sequence[str]:
    """The line that says a ticket is not the head of ``slots next``.

    Args:
        found: the startable items of the queue, read just now, in order.
        labels: the priority labels, highest first.
        ticket: the ticket whose brief is printed, as ``owner/repo#N``.
        given: the configuration as the command was given it.

    Returns:
        One line when the ticket is queued behind another first startable item,
        else none (a ticket outside the queue is not ranked).
    """
    order = [each.reference for each in found]
    if ticket not in order or order[0] == ticket:
        return []
    head = found[0]
    place = f"rank {order.index(ticket) + 1}"
    return [
        f"{Marker.NOT_THE_HEAD.text}: {ticket} is {place}; the head is"
        f" {head.reference} ({_label(head, labels)}, opened {head.created_at[:10]});"
        f" its brief: pitboss slots next {head.reference} --config {given}"
    ]

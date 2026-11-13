"""The lines about the rank of a ticket: BLOCKED, SUPERSEDED, BLOCKS.

Shared by ``slots next``, ``next`` and the sweep (keyword: ticket-blocked,
blocks-line, superseded-ticket; pitboss#388).
"""

from typing import Iterable, Mapping, Protocol, Sequence

from . import blockedline
from .markers import Marker

TICKET = "NEW_PR"


class Kind(Protocol):
    """A category of work, read by its name."""

    @property
    def name(self) -> str:
        """The category's name.

        Returns:
            ``NEW_PR`` for a ticket that waits for a worker.
        """


class Ranked(Protocol):
    """What the lines read of an item."""

    @property
    def category(self) -> Kind:
        """The kind of work.

        Returns:
            The category.
        """

    @property
    def reference(self) -> str:
        """The item's ``owner/name#number``.

        Returns:
            The reference.
        """

    @property
    def body(self) -> str:
        """A ticket's text, or the allowlist line a PR's red check asks for.

        Returns:
            The text.
        """

    @property
    def blockers(self) -> Sequence[str]:
        """What it waits for.

        Returns:
            The open blockers.
        """

    @property
    def ticket(self) -> str:
        """The ticket a PR fixes, or "".

        Returns:
            The ticket's reference.
        """

    @property
    def priority(self) -> int:
        """The index of its priority label.

        Returns:
            The index.
        """

    @property
    def created_at(self) -> str:
        """When it was opened.

        Returns:
            An ISO timestamp.
        """


class Offer(Protocol):
    """What an offer holds for the lines."""

    @property
    def items(self) -> Sequence[Ranked]:
        """The offered items.

        Returns:
            The items.
        """

    @property
    def blocked(self) -> Sequence[Ranked]:
        """The items with an open blocker.

        Returns:
            The items.
        """

    @property
    def superseded(self) -> Sequence[Ranked]:
        """The superseded tickets.

        Returns:
            The items.
        """

    @property
    def blocks(self) -> Mapping[str, Sequence[str]]:
        """What waits for each dependency that was offered ahead of it.

        Returns:
            The references that wait, by the dependency's.
        """

    @property
    def labels(self) -> Sequence[str]:
        """The priority labels.

        Returns:
            The labels, highest priority first.
        """



def _name(item: Ranked) -> str:
    # a ticket, or the ticket a PR fixes with the PR after it
    if item.category.name == TICKET or not item.ticket:
        return item.reference
    return f"{item.ticket} (PR {item.reference})"


def _blocks(item: Ranked, waits: Sequence[str], offer: Offer) -> str:
    # ranked with the oldest item that waits, whether a PR stands for the blocker or not
    waiting = [each for each in offer.blocked if each.reference in waits]
    oldest = min(waiting, key=lambda each: each.created_at, default=item)
    ranked = f"ranked {offer.labels[oldest.priority]}, opened {oldest.created_at[:10]}"
    return f"{Marker.BLOCKS.text} {_name(item)}: blocks {', '.join(waits)}; {ranked}"


def lines(offer: Offer) -> Iterable[str]:
    """The blocked, superseded and blocking lines of an offer.

    Args:
        offer: the queued work and the tickets kept back, in whole.

    Yields:
        ``BLOCKED`` for each blocked ticket (and PR), ``SUPERSEDED`` for each
        superseded ticket, ``BLOCKS`` for each offered item that others wait
        for.
    """
    for waiting in offer.blocked:
        yield blockedline.of(waiting)
    for gone in offer.superseded:
        yield f"{Marker.SUPERSEDED.text} {gone.reference}"
    for first in offer.items:
        if first.reference in offer.blocks:
            yield _blocks(first, offer.blocks[first.reference], offer)

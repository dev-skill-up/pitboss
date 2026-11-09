"""The lines about the rank of a ticket: BLOCKED, SUPERSEDED, BLOCKS, PROMOTE.

Shared by ``slots next``, ``next`` and the sweep (keyword: ticket-blocked,
blocks-line, superseded-ticket, promote; pitboss#388).
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
    def blockers(self) -> Sequence[str]:
        """What it waits for.

        Returns:
            The open blockers.
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

    @property
    def promoted(self) -> Sequence[str]:
        """The promote lines.

        Returns:
            The lines.
        """


def _blocks(item: Ranked, waits: Sequence[str], labels: Sequence[str]) -> str:
    ranked = "ranked with the oldest of them"
    if item.category.name == TICKET:
        ranked = f"ranked {labels[item.priority]}, opened {item.created_at[:10]}"
    return f"{Marker.BLOCKS.text} {item.reference}: blocks {', '.join(waits)}; {ranked}"


def lines(offer: Offer) -> Iterable[str]:
    """The blocked, superseded, blocking and promoted lines of an offer.

    Args:
        offer: the queued work and the tickets kept back, in whole.

    Yields:
        ``BLOCKED`` for each blocked ticket (and PR), ``SUPERSEDED`` for each
        superseded ticket, ``BLOCKS`` for each offered item that others wait
        for, then the ``PROMOTE`` lines.
    """
    for waiting in offer.blocked:
        yield blockedline.of(waiting)
    for gone in offer.superseded:
        yield f"{Marker.SUPERSEDED.text} {gone.reference}"
    for first in offer.items:
        if first.reference in offer.blocks:
            yield _blocks(first, offer.blocks[first.reference], offer.labels)
    yield from offer.promoted

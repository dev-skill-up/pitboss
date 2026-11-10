"""The first stage of the order over a window of tickets (keyword: ticket-window).

``slots next`` shows the top of the order, so it reads the first tickets of it
(``ticketwindow``) and the tickets two others name as a cause, which rank first
(keyword: promote, pitboss#388), and nothing else (pitboss#443).
"""

import dataclasses
import datetime
from typing import AbstractSet, Mapping, Protocol, Sequence

from . import (
    causecache,
    config,
    ghapi,
    ledger,
    promotion,
    pulls,
    slotcache,
    ticketitem,
    ticketwindow,
    work,
    workitem,
)


class Reading(Protocol):
    """The part of a command's context that the stage reads with."""

    @property
    def github(self) -> ghapi.GitHub:
        """The API.

        Returns:
            The API.
        """

    @property
    def settings(self) -> config.Config:
        """The configuration.

        Returns:
            The configuration.
        """

    @property
    def now(self) -> datetime.datetime:
        """The time of the run.

        Returns:
            The time.
        """


def tickets(found: Reading, taken: AbstractSet[str], count: int) -> Sequence[work.Item]:
    """The first ``count`` open tickets of the order that no open PR names.

    Args:
        found: the context.
        taken: the tickets open PRs already work on.
        count: how many tickets to read.

    Returns:
        The items, the oldest of the highest priority first.
    """
    settings = found.settings
    window = ticketwindow.window(
        found.github,
        ticketwindow.Asked(
            repos=config.repositories(settings),
            labels=settings.slots.priority_labels,
            skip=taken,
        ),
        count,
    )
    return [
        workitem.of_ticket(each.reference, each.issue, each.priority) for each in window
    ]


def _caused(found: Reading) -> Mapping[str, Sequence[str]]:
    # the tickets two or more others name as a cause, from what changed since last time
    slots = found.settings.slots
    cache = slotcache.path_of(slots.ledger)
    parts = slotcache.read(cache)
    kept = parts.get(causecache.CAUSES)
    pairs, now = causecache.causes(
        found.github,
        config.repositories(found.settings),
        kept if isinstance(kept, dict) else {},
        found.now,
    )
    slotcache.write(cache, {**parts, causecache.CAUSES: now})
    return promotion.heavy(pairs, frozenset(slots.owner_priorities))


def _ranked(slots: config.Slots, item: work.Item) -> work.Item:
    # a ticket read by itself ranks by the first of the priority labels it has
    having = [
        at for at, each in enumerate(slots.priority_labels) if each in item.labels
    ]
    return dataclasses.replace(item, priority=min(having, default=-1))


def _outside(
    found: Reading,
    named: Mapping[str, Sequence[str]],
    listed: AbstractSet[str],
    away: AbstractSet[str],
) -> Sequence[work.Item]:
    # the tickets named as a cause that the window did not reach, read by themselves
    wanted = [
        each
        for each in named
        if each not in listed and each not in away and config.has(found.settings, each)
    ]
    read = (ticketitem.read(found.github, each) for each in wanted)
    return [_ranked(found.settings.slots, each) for each in read if each is not None]


def promoted(
    found: Reading, queued: Sequence[work.Item], away: AbstractSet[str]
) -> tuple[Sequence[work.Item], Sequence[str]]:
    """The queued work with the tickets named as a cause ranked first.

    Args:
        found: the context.
        queued: the queued work, a window of tickets.
        away: the tickets open PRs already work on.

    Returns:
        The items in order, and the ``PROMOTE`` lines.
    """
    labels = found.settings.slots.priority_labels
    named = _caused(found)
    listed = {each.reference for each in queued}
    items = [*queued, *_outside(found, named, listed, away)]
    new = work.Category.NEW_PR
    below = {
        each.reference: named[each.reference]
        for each in items
        if each.category is new and each.priority > 0 and each.reference in named
    }
    kept = [
        each for each in items if each.reference in listed or each.reference in below
    ]
    raised, said = promotion.raised(kept, below, labels)
    return work.ordered(raised, ()), said


def start(
    found: Reading, opened: Sequence[pulls.Read], book: ledger.Ledger, count: int
) -> tuple[Sequence[work.Item], Sequence[str], bool]:
    """The queued work over a window of tickets, ranked.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the ledger.
        count: how many tickets to read.

    Returns:
        The items, the ``PROMOTE`` lines and whether tickets beyond the window
        are queued.
    """
    away = work.taken(pulls.readable(opened))
    read = tickets(found, away, count)
    listed = work.assemble(opened, read, book)
    items, said = promoted(found, ticketitem.fixing(listed, opened), away)
    return items, said, len(read) >= count

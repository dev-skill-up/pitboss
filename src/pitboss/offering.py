"""What is offered to start: the queued work, less what is kept back.

Kept back are the tickets of a repository under the owner's hold, the tickets
that cannot be worked on until an open ticket or PR (keyword: ticket-blocked)
with the PRs of such tickets (blocked-pull), and the superseded tickets; the open
ticket a blocked ticket or PR waits for is offered in its place (``dependency``,
pitboss#280, pitboss#388). A ticket named as a cause by many others ranks first
(``promotion``). Shared by ``slots next``, ``next`` and the sweep, so the three
agree on which tickets are offered.
"""

import argparse
import dataclasses
import functools
from typing import AbstractSet, Callable, Iterable, Mapping, Protocol, Sequence

from . import (
    blockers,
    concurrently,
    config,
    configfile,
    dependency,
    ghapi,
    holds,
    ledger,
    promotion,
    pulls,
    shapes,
    ticketitem,
    work,
)


def apart(
    items: Sequence[work.Item], standing: Mapping[str, int], gone: AbstractSet[str]
) -> work.Offered:
    """Keep apart the tickets of held repositories, the blocked and the superseded.

    Args:
        items: the ordered items (``work.queued``, with their blockers named).
        standing: the held repositories and their open counts (``holds``).
        gone: the superseded tickets.

    Returns:
        The items to start, the tickets held back, the tickets (and PRs) blocked
        and the tickets superseded.
    """
    held = [each for each in items if _is_held(each, standing)]
    rest = [each for each in items if each not in held]
    return work.Offered(
        items=[
            each for each in rest if not each.blockers and each.reference not in gone
        ],
        held=held,
        standing=standing,
        blocked=[each for each in rest if each.blockers],
        superseded=[each for each in rest if each.reference in gone],
    )


def _is_held(item: work.Item, standing: Mapping[str, int]) -> bool:
    in_held = item.reference.rpartition("#")[0] in standing
    return in_held and item.category == work.Category.NEW_PR


class Source(Protocol):
    """The part of a command's context that the offer reads."""

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
    def args(self) -> argparse.Namespace:
        """The parsed arguments.

        Returns:
            The arguments.
        """


def _slug(each: pulls.Read) -> str:
    # an unreadable PR is open too, and its reference names its repository
    if isinstance(each, shapes.Unreadable):
        return each.reference.rpartition("#")[0]
    return each.repo.slug


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Look:
    """What the offer is made from.

    Attributes:
        opened: the open PRs, read or not.
        marks: the blocked PRs (``pullmarks.pull_marks``).
        staged: reads the queued work of a window of tickets instead of all of
            them (keyword: ticket-window, pitboss#443): the items, the
            ``PROMOTE`` lines and whether tickets beyond the window are queued.
    """

    opened: Sequence[pulls.Read]
    marks: Mapping[str, work.Item]
    staged: Callable[[], tuple[Sequence[work.Item], Sequence[str], bool]] | None = None


def _start(
    found: Source, scope: Look, book: ledger.Ledger
) -> tuple[Sequence[work.Item], Sequence[str], bool]:
    # the queued work, ranked by the cause rule, and whether tickets were left unread
    if scope.staged is not None:
        return scope.staged()
    listed = work.queued(scope.opened, found.github, found.settings, book)
    items, said = _promoted(found, ticketitem.fixing(listed, scope.opened))
    return items, said, False


def standing(found: Source, slugs: Sequence[str]) -> Mapping[str, int]:
    """The repositories the owner holds, with their open PRs.

    Args:
        found: the context.
        slugs: the repository of each open PR.

    Returns:
        Each held repository and its open count (``holds.standing``).
    """
    owned = configfile.load_holds(
        configfile.named(found.args),
        configfile.working_directory(found.args),
        found.settings.project.repo.owner,
    )
    return holds.standing(owned, slugs)


def offered(found: Source, scope: Look, book: ledger.Ledger) -> work.Offered:
    """The work to start, and the tickets the hold and an open blocker keep back.

    Args:
        found: the context.
        scope: the open PRs, the blocked ones and how to read the tickets.
        book: the slot ledger.

    Returns:
        The queued work, the held, blocked and superseded tickets apart; its
        ``unread`` says that tickets beyond the window were not read.
    """
    opened, marks = scope.opened, scope.marks
    held = standing(found, [_slug(each) for each in opened])
    queued, said, unread = _start(found, scope, book)
    queued = ranked(found, opened, book, queued)
    queued = _blocked_pulls(queued, marks, book, opened)
    named, gone = _named(found, queued)
    settled, waiting = _dependencies_first(found, opened, book, named)
    offer = apart(settled, held, gone)
    labels = found.settings.slots.priority_labels
    return dataclasses.replace(
        offer, promoted=said, blocks=waiting, labels=labels, unread=unread
    )


def _marked(found: Source, item: work.Item) -> tuple[work.Item, bool]:
    # the open blockers a ticket names, and whether it is superseded
    if item.category is not work.Category.NEW_PR:
        return item, False
    found_blockers, gone = blockers.waiting(
        found.github, found.settings, item, item.reference
    )
    return dataclasses.replace(item, blockers=found_blockers), gone


def _named(
    found: Source, queued: Sequence[work.Item]
) -> tuple[Sequence[work.Item], AbstractSet[str]]:
    # the blockers of each ticket named, and the tickets that are superseded
    both = concurrently.each(functools.partial(_marked, found), queued)
    return [each for each, _ in both], {each.reference for each, gone in both if gone}


def _promoted(
    found: Source, queued: Sequence[work.Item]
) -> tuple[Sequence[work.Item], Sequence[str]]:
    # keyword: promote (pitboss#388): a ticket many others name as a cause ranks first
    slots = found.settings.slots
    new = work.Category.NEW_PR
    tickets = [each for each in queued if each.category is new]
    sources = promotion.sources(found.github, config.repositories(found.settings))
    below = [each.reference for each in tickets if each.priority > 0]
    named = promotion.named_by(below, sources, frozenset(slots.owner_priorities))
    items, said = promotion.raised(queued, named, slots.priority_labels)
    return work.ordered(items, ()), said


def _blocked_pulls(
    queued: Sequence[work.Item],
    stands: Mapping[str, work.Item],
    book: ledger.Ledger,
    opened: Sequence[pulls.Read],
) -> Sequence[work.Item]:
    # keyword: blocked-pull: a blocked PR is an item with blockers, whatever its step;
    # one with no round is placed among the PRs by its own age, then ranks as its ticket
    listed = {each.reference for each in queued}
    own = {pulls.reference(e): e.pull.created_at for e in pulls.readable(opened)}
    extra = [
        dataclasses.replace(each, created_at=own.get(reference, each.created_at))
        for reference, each in stands.items()
        if reference not in listed
    ]
    ordered = work.ordered([*queued, *extra], _agents(book)) if extra else queued
    return [stands.get(each.reference, each) for each in ordered]


def _open_ticket(found: Source, reference: str, waiting: work.Item) -> work.Item | None:
    # keyword: ticket-blocked: the ticket stands in the place of the one that waits
    item = ticketitem.read(found.github, reference)
    if item is None:
        return None
    named, superseded = _marked(found, item)
    return None if superseded else named


def _stated(
    found: Source, busy: AbstractSet[str], items: Sequence[work.Item]
) -> Mapping[str, work.Item]:
    # keyword: owner-priority (pitboss#371): the tickets the owner ranks, by that rank
    slots = found.settings.slots
    new = work.Category.NEW_PR
    tickets = {each.reference: each for each in items if each.category is new}

    def rank(reference: str, label: str) -> work.Item | None:
        ticket = tickets.get(reference) or ticketitem.read(found.github, reference)
        return ticket and dataclasses.replace(
            ticket, priority=slots.priority_labels.index(label)
        )

    wanted = [
        (reference, label)
        for reference, label in slots.owner_priorities.items()
        if reference not in busy and config.has(found.settings, reference)
    ]
    return {ref: made for ref, label in wanted if (made := rank(ref, label))}


def ranked(
    found: Source,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
    items: Sequence[work.Item],
) -> Sequence[work.Item]:
    """The queued work, with the tickets the owner ranks given that rank.

    A ticket an open PR works on, or a slot holds, keeps no rank; while a PR
    cannot be read no ticket is offered (keyword: unreadable-pull), so none is
    added.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the ledger.
        items: the queued work (``work.queued``).

    Returns:
        The items, in order.
    """
    facts = pulls.readable(opened)
    if not found.settings.slots.owner_priorities or len(facts) != len(opened):
        return items
    agents = _agents(book)
    stated = _stated(found, work.taken(facts) | set(agents), items)
    rest = [each for each in items if each.reference not in stated]
    return work.ordered([*rest, *stated.values()], agents)


def _agents(book: ledger.Ledger) -> Sequence[str]:
    return [each.task for each in book.slots if each.agent]


UNREAD = "OWNER PRIORITY UNREAD: {reference} = {label}: {why}"


def _stated_ticket(
    found: Source, offer: work.Offered, reference: str
) -> blockers.Ticket | str:
    # the ticket the owner states a priority for, or why it cannot be read
    if not config.has(found.settings, reference):
        return "its repository is not configured"
    for each in [*offer.items, *offer.held, *offer.blocked, *offer.superseded]:
        if each.reference == reference and each.category is work.Category.NEW_PR:
            return blockers.Ticket(open=True, labels=each.labels)
    ticket = blockers.read(found.github, reference)
    if ticket is None:
        return "the ticket cannot be read"
    return "it is a PR, not a ticket" if ticket.pull else ticket


def _disagrees(reference: str, label: str, ticket: blockers.Ticket | str) -> str:
    # the line for one stated priority, or "" when the ticket agrees or is closed
    if isinstance(ticket, str):
        return UNREAD.format(reference=reference, label=label, why=ticket)
    if not ticket.open or label in ticket.labels:
        return ""
    has = ", ".join(sorted(ticket.labels)) or "no label"
    return (
        f"LABEL DISAGREES: {reference} is labelled {has},"
        f" the owner's stated priority is {label}"
    )


def disagreements(found: Source, offer: work.Offered) -> Iterable[str]:
    """The line of each ticket whose label is not the owner's stated priority.

    Every ticket the owner states a priority for is read, also one that an open
    PR works on or a slot holds. The line has no entry in ``markers.Marker``: the
    references explain each of those, and this change adds no line to a reference
    (keyword: owner-priority).

    Args:
        found: the context.
        offer: the queued work, the held and the blocked tickets.

    Returns:
        ``LABEL DISAGREES: <ticket> is labelled <labels>, the owner's stated
        priority is <label>``, in the order of the configuration; for a stated
        priority that cannot be used (a repository that is not configured, a
        ticket that cannot be read or is a PR) ``OWNER PRIORITY UNREAD:
        <ticket> = <label>: <why>``. A closed ticket has no line.
    """
    stated = found.settings.slots.owner_priorities.items()
    said = (
        _disagrees(ref, label, _stated_ticket(found, offer, ref))
        for ref, label in stated
    )
    return [line for line in said if line]


def _dependencies_first(
    found: Source,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
    tickets: Sequence[work.Item],
) -> tuple[Sequence[work.Item], Mapping[str, Sequence[str]]]:
    # keyword: ticket-blocked (pitboss#280): a dependency is offered ahead of it
    readable = pulls.readable(opened)
    unavailable = work.taken(readable) | set(_agents(book))
    # an unreadable PR may work on any ticket (keyword: unreadable-pull)
    unread = len(readable) != len(opened)
    read = None if unread else functools.partial(_open_ticket, found)
    return dependency.settle(tickets, read, unavailable, _placed)


def _placed(found: work.Item, oldest: work.Item) -> work.Item:
    # keyword: ticket-blocked: a dependency moved ahead of the oldest ticket that waits
    # for it takes that ticket's priority and age
    return dataclasses.replace(
        found, priority=oldest.priority, created_at=oldest.created_at
    )

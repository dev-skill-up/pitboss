"""What is offered to start: the queued work, less what is kept back.

Kept back are the tickets of a repository under the owner's hold (keyword:
pr-hold) and the tickets that cannot be worked on until an open ticket or PR
(keyword: ticket-blocked); the open ticket a blocked ticket waits for is offered
ahead of it (``dependency``, pitboss#280). Shared by ``slots next``, ``next`` and
the sweep, so the three agree on which tickets are offered.
"""

import argparse
import dataclasses
import functools
from typing import Mapping, Protocol, Sequence

from . import (
    blockers,
    concurrently,
    config,
    configfile,
    dependency,
    ghapi,
    holds,
    ledger,
    pulls,
    shapes,
    ticketblock,
    work,
)


def apart(items: Sequence[work.Item], standing: Mapping[str, int]) -> work.Offered:
    """Keep apart the tickets of the repositories the owner holds, and the blocked.

    Args:
        items: the ordered items (``work.queued``, with their blockers named).
        standing: the held repositories and their open counts (``holds``).

    Returns:
        The items to start, the tickets held back and the tickets blocked.
    """
    held = [each for each in items if _is_held(each, standing)]
    rest = [each for each in items if each not in held]
    return work.Offered(
        items=[each for each in rest if not each.blocker],
        held=held,
        standing=standing,
        blocked=[each for each in rest if each.blocker],
    )


def _is_held(item: work.Item, standing: Mapping[str, int]) -> bool:
    in_held = item.reference.rpartition("#")[0] in standing
    return in_held and item.category == work.Category.NEW_PR


def marked(github: ghapi.GitHub, settings: config.Config, item: work.Item) -> work.Item:
    """Name the open ticket or PR a ticket says it cannot be worked on until.

    The body and the trusted comments of a ticket are read for ``Cannot be
    worked on until <owner/repo#n>``, ``Blocked by <owner/repo#n>`` or
    ``Depends on <owner/repo#n>``; a blocker that is closed or merged blocks
    nothing.

    Args:
        github: the API.
        settings: the configuration.
        item: a PR or a ticket.

    Returns:
        The item, with ``blocker`` set when it is a ticket with an open blocker.
    """
    if item.category is not work.Category.NEW_PR:
        return item
    slug = item.reference.rpartition("#")[0]
    trusted = settings.review.trusted
    read = ticketblock.comments_of if item.comments else None
    found = [item.body, *(read(github, item.reference, trusted) if read else ())]
    repo = config.make_repo(*slug.split("/", 1))

    def is_open(reference: str) -> bool:
        ticket = blockers.read(github, reference)
        return ticket is not None and ticket.open

    blocker = ticketblock.open_blocker(repo, found, is_open)
    return dataclasses.replace(item, blocker=blocker)


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


def offered(
    found: Source, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> work.Offered:
    """The work to start, and the tickets the hold and an open blocker keep back.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger.

    Returns:
        The queued work, the held and the blocked tickets apart.
    """
    owned = configfile.load_holds(
        configfile.named(found.args),
        configfile.working_directory(found.args),
        found.settings.project.repo.owner,
    )
    held = holds.standing(owned, [_slug(each) for each in opened])
    queued = work.queued(opened, found.github, found.settings, book)
    tickets = concurrently.each(
        lambda item: marked(found.github, found.settings, item), queued
    )
    return apart(_dependencies_first(found, opened, book, tickets), held)


def _open_ticket(found: Source, reference: str, waiting: work.Item) -> work.Item | None:
    # keyword: ticket-blocked: a blocker inherits the priority and age it blocks
    ticket = blockers.read(found.github, reference)
    if ticket is None or not ticket.open or ticket.pull:
        return None
    item = work.Item(
        category=work.Category.NEW_PR,
        reference=reference,
        created_at=waiting.created_at,
        title=ticket.title,
        priority=waiting.priority,
        labels=ticket.labels,
        body=ticket.body,
        comments=ticket.comments,
    )
    return marked(found.github, found.settings, item)


def _dependencies_first(
    found: Source,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
    tickets: Sequence[work.Item],
) -> Sequence[work.Item]:
    # keyword: ticket-blocked (pitboss#280): a dependency is offered ahead of it
    readable = pulls.readable(opened)
    unavailable = work.taken(readable) | {s.task for s in book.slots if s.agent}
    # an unreadable PR may work on any ticket (keyword: unreadable-pull)
    if len(readable) != len(opened):
        return dependency.order(tickets)
    read = functools.partial(_open_ticket, found)
    return dependency.order(dependency.join(tickets, read, unavailable))

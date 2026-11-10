"""A ticket as the item it is queued as, and a PR as the ticket it stands for."""

import dataclasses
from typing import Sequence

from . import fixnames, ghapi, pulls, ticketdata, workitem


def read(github: ghapi.GitHub, reference: str) -> workitem.Item | None:
    """An open ticket, as the item it is queued as; a PR and a closed ticket are not.

    Args:
        github: the API.
        reference: ``owner/name#number``.

    Returns:
        The item, or None.
    """
    ticket = ticketdata.open_ticket(github, reference)
    return (
        None if ticket is None or ticket.pull else workitem.of_ticket(reference, ticket)
    )


def fixing(
    queued: Sequence[workitem.Item], opened: Sequence[pulls.Read]
) -> Sequence[workitem.Item]:
    """The items, each PR standing for the ticket it fixes.

    Args:
        queued: the queued work.
        opened: the open PRs, read or not.

    Returns:
        The items, with the ticket of each PR set (keyword: ticket-blocked,
        blocked-pull).
    """
    named = {
        pulls.reference(e): fixnames.first_fixed(e.pull.body or "", e.repo)
        for e in pulls.readable(opened)
    }
    return [
        dataclasses.replace(each, ticket=named.get(each.reference, each.ticket))
        for each in queued
    ]

"""A ticket as ``issues/<number>`` gives it, read by itself (pitboss#162, #443).

Kept apart from ``blockers``, which also reads PRs, so that the modules that only
read a ticket need not depend on the reading of every PR.
"""

import dataclasses
import json
from typing import AbstractSet

from . import ghapi, ticketread


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """A ticket as ``issues/<number>`` gives it.

    Attributes:
        open: whether it is open.
        labels: its labels' names.
        body: its text (keyword: done-when-names).
        title: its title.
        created_at: when it was opened (ISO 8601).
        comments: how many comments it has.
        pull: whether it is a PR (``issues/<number>`` answers for both).
        merged_at: when the PR merged (ISO 8601), else empty (keyword: blocked-by).
    """

    open: bool
    labels: AbstractSet[str]
    body: str = ""
    title: str = ""
    created_at: str = ""
    comments: int = 0
    pull: bool = False
    merged_at: str = ""


def read(github: ghapi.GitHub, reference: str) -> Ticket | None:
    """Read a ticket.

    Args:
        github: the API.
        reference: ``owner/name#number``.

    Returns:
        The ticket, or None when the API cannot give it.
    """
    text = ticketread.text(github, reference)
    if text is None:
        return None
    item = json.loads(text)
    listed = item.get("labels", ())
    return Ticket(
        open=item["state"] == "open",
        labels=frozenset(str(label["name"]) for label in listed),
        body=item.get("body") or "",
        title=item.get("title") or "",
        created_at=item.get("created_at") or "",
        comments=int(item.get("comments") or 0),
        pull="pull_request" in item,
        merged_at=(item.get("pull_request") or {}).get("merged_at") or "",
    )


def open_ticket(github: ghapi.GitHub, reference: str) -> Ticket | None:
    """Read a ticket that is open.

    Args:
        github: the API.
        reference: ``owner/name#number``.

    Returns:
        The ticket, or None when it is closed, merged or cannot be read.
    """
    ticket = read(github, reference)
    return ticket if ticket is not None and ticket.open else None

"""The one order of work, read lazily from the listings (keyword: one-path).

The open pull requests that are not relock reviews, oldest first; then the tickets
by priority label and age, a label's first page of each repository merged by age
and a later page read only when the merge has used up the one before; then the
relock pull requests (keyword: relock-last). Nothing here reads an item's details:
the walk (``readworld``) examines an item only when it reaches it.
"""

import dataclasses
import heapq
import json
from typing import Iterator, Mapping, Sequence

from . import (
    concurrently,
    config,
    configrepos,
    ghapi,
    issuelist,
    ledger,
    listed,
    shapes,
    ticketdata,
)

STOP = 5  # the least number of decisions a walk stops at
Items = Sequence[shapes.Issue | None]  # a page's raw items (none for a pull request)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """A ticket the walk reached.

    Attributes:
        reference: its ``owner/name#number``.
        issue: the ticket as listed.
        priority: the index of the label it is ranked by.
    """

    reference: str
    issue: shapes.Issue
    priority: int


Candidate = listed.Listed | Ticket


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FullPage:
    """A page as long as a page can be: there may be one after it.

    Attributes:
        items: the page's raw items (none for a pull request).
        following: the number of the page after it.
    """

    items: Items
    following: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class LastPage:
    """A page shorter than a page can be: the list ends with it.

    Attributes:
        items: the page's raw items (none for a pull request).
    """

    items: Items


Page = FullPage | LastPage


def stop_count(book: ledger.Ledger) -> int:
    """The number of decisions a walk stops at: ``max(5, the slots configured)``.

    Args:
        book: the ledger, one row for each slot.

    Returns:
        The count.
    """
    return max(STOP, len(book.slots))


def _rows(text: str) -> Sequence[Mapping[str, object]]:
    found = json.loads(text)
    return [each for each in found if isinstance(each, dict)]


def listing(github: ghapi.GitHub, settings: config.Config) -> Sequence[listed.Listed]:
    """Every open pull request of the configuration, oldest first.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        The listing rows: one listing of each repository, read at once.
    """
    repos = configrepos.repositories(settings)
    pages = concurrently.each(
        lambda repo: ghapi.pages(github, f"repos/{repo.slug}/pulls?state=open", _rows),
        repos,
    )
    prefix = settings.lint.relock_prefix
    rows = [
        listed.listed_row(repo, prefix, row)
        for repo, got in zip(repos, pages)
        for row in got
    ]
    return sorted(rows, key=lambda each: each.created_at)


def _page(github: ghapi.GitHub, path: str, number: int) -> Page:
    items = issuelist.listed(
        ghapi.get(github, f"{path}&per_page={ghapi.PAGE_SIZE}&page={number}")
    )
    if len(items) == ghapi.PAGE_SIZE:
        return FullPage(items=items, following=number + 1)
    return LastPage(items=items)


def _stream(github: ghapi.GitHub, path: str) -> Iterator[shapes.Issue]:
    # a page is raw items (the list holds pull requests): a full one may have more
    page = _page(github, path, 1)
    while isinstance(page, FullPage):
        yield from filter(None, page.items)
        page = _page(github, path, page.following)
    yield from filter(None, page.items)


def _chained(
    first: shapes.Issue, rest: Iterator[shapes.Issue]
) -> Iterator[shapes.Issue]:
    yield first
    yield from rest


def _primed(github: ghapi.GitHub, path: str) -> Iterator[shapes.Issue]:
    # the stream with its first page read now, so the first pages read at once
    stream = _stream(github, path)
    first = next(stream, None)
    return iter(()) if first is None else _chained(first, stream)


def labelled_path(repo: str, label: str) -> str:
    """The one listing of a label's open issues, oldest first (P9).

    Args:
        repo: ``owner/name``.
        label: the label.

    Returns:
        The path.
    """
    return f"repos/{repo}/issues?state=open&labels={label}&sort=created&direction=asc"


def _label_stream(
    github: ghapi.GitHub, repos: Sequence[config.Repo], label: str
) -> Iterator[tuple[str, shapes.Issue]]:
    # the open tickets of a label, oldest first, across repositories: the first
    # page of every repository at once, the others when the merge reaches them
    firsts = concurrently.each(
        lambda repo: _primed(github, labelled_path(repo.slug, label)), repos
    )
    streams = [_named(repo, first) for repo, first in zip(repos, firsts)]
    return heapq.merge(*streams, key=lambda pair: pair[1].created_at)


def _named(
    repo: config.Repo, issues: Iterator[shapes.Issue]
) -> Iterator[tuple[str, shapes.Issue]]:
    # each issue of one repository's stream with its reference, bound to that one
    for each in issues:
        yield "#".join((repo.slug, str(each.number))), each


def issue_of(reference: str, ticket: ticketdata.Ticket) -> shapes.Issue:
    """A ticket read by reference, as a listing gives a ticket.

    Args:
        reference: its ``owner/name#number``.
        ticket: what was read of it.

    Returns:
        The issue.
    """
    return shapes.Issue(
        number=int(reference.partition("#")[2]),
        title=ticket.title,
        created_at=ticket.created_at,
        labels=ticket.labels,
        body=ticket.body,
        comments=ticket.comments,
    )


def _owner_stated(
    github: ghapi.GitHub, settings: config.Config, label: str
) -> Iterator[tuple[str, shapes.Issue]]:
    # the open tickets the owner ranks by this label, oldest first
    stated = sorted(
        reference
        for reference, named in settings.slots.owner_priorities.items()
        if named == label
    )
    found = [(each, ticketdata.open_ticket(github, each)) for each in stated]
    opened = [
        (reference, issue_of(reference, ticket))
        for reference, ticket in found
        if ticket is not None and not ticket.pull
    ]
    return iter(sorted(opened, key=lambda pair: pair[1].created_at))


def _labelled(
    github: ghapi.GitHub, settings: config.Config, label: str
) -> Iterator[tuple[str, shapes.Issue]]:
    # a label's tickets: its listing and the owner's, merged by age; a ticket the
    # owner ranks by another label is in that label only
    stated = settings.slots.owner_priorities
    merged = heapq.merge(
        _label_stream(github, configrepos.repositories(settings), label),
        _owner_stated(github, settings, label),
        key=lambda pair: pair[1].created_at,
    )
    return (pair for pair in merged if stated.get(pair[0], label) == label)


def tickets(github: ghapi.GitHub, settings: config.Config) -> Iterator[Ticket]:
    """The open tickets of the priority labels, by label, then oldest first.

    A ticket the owner ranks (``owner_priorities``) is in the label the owner
    states, and in no other.

    Args:
        github: the API.
        settings: the configuration.

    Yields:
        Each ticket, once, read only when the walk reaches it.
    """
    seen: set[str] = set()
    for priority, label in enumerate(settings.slots.priority_labels):
        for reference, issue in _labelled(github, settings, label):
            if reference not in seen:
                seen.add(reference)
                yield Ticket(reference=reference, issue=issue, priority=priority)


def candidates(
    github: ghapi.GitHub, settings: config.Config, rows: Sequence[listed.Listed]
) -> Iterator[Candidate]:
    """The order of work, lazily: what the walk may examine, first to take first.

    Args:
        github: the API.
        settings: the configuration.
        rows: the listing rows, oldest first.

    Yields:
        The pull requests that are not relock reviews, then the tickets, then
        the relock pull requests (keyword: relock-last).
    """
    yield from (each for each in rows if not each.relock)
    yield from tickets(github, settings)
    yield from (each for each in rows if each.relock)

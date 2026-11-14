"""The tickets of the order of work, read lazily from the searches (one-path).

The order is the open pull requests that are not relock reviews (``pullsearch``),
then the tickets by priority label and age, a label's first page of each
organisation merged by age and a later page read only when the merge has used up
the one before, then the relock pull requests (keyword: relock-last). Each read is
a search of one organisation, filtered here to the configured repositories
(keyword: org-search), so no read is made for each repository. Nothing here reads
an item's details: the walk (``readworld``) examines an item only when it reaches it.
"""

import dataclasses
import heapq
from typing import Iterator, Mapping, Sequence

from . import concurrently, config, ghapi, issuelist, ledger, listed, orgsearch
from . import shapes, ticketdata

STOP = 5  # the least number of decisions a walk stops at
Found = tuple[str, shapes.Issue]  # a ticket's reference, and the ticket
Items = Sequence[Found | None]  # a page's raw items (none for another repository's)


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
        items: the page's raw items (none for another repository's).
        following: the number of the page after it.
    """

    items: Items
    following: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class LastPage:
    """A page shorter than a page can be: the list ends with it.

    Attributes:
        items: the page's raw items (none for another repository's).
    """

    items: Items


Page = FullPage | LastPage
Repos = Mapping[str, config.Repo]  # the configured repositories by owner/name


def stop_count(book: ledger.Ledger) -> int:
    """The number of decisions a walk stops at: ``max(5, the slots configured)``.

    Args:
        book: the ledger, one row for each slot.

    Returns:
        The count.
    """
    return max(STOP, len(book.slots))


def _found(item: orgsearch.Item, known: Repos) -> Found | None:
    # a ticket of a configured repository, with its reference
    repo, issue = orgsearch.repo_of(item, known), issuelist.issue_of(item)
    return (f"{repo.slug}#{issue.number}", issue) if repo and issue else None


def _page(github: ghapi.GitHub, path: str, number: int, repos: Repos) -> Page:
    asked = f"{path}&per_page={ghapi.PAGE_SIZE}&page={number}"
    items = [_found(each, repos) for each in orgsearch.items(ghapi.get(github, asked))]
    if len(items) == ghapi.PAGE_SIZE:
        return FullPage(items=items, following=number + 1)
    return LastPage(items=items)


def _stream(github: ghapi.GitHub, path: str, repos: Repos) -> Iterator[Found]:
    # a page is raw items (the search holds other repositories): a full one may
    # have more
    page = _page(github, path, 1, repos)
    while isinstance(page, FullPage):
        yield from filter(None, page.items)
        page = _page(github, path, page.following, repos)
    yield from filter(None, page.items)


def _chained(first: Found, rest: Iterator[Found]) -> Iterator[Found]:
    yield first
    yield from rest


def _primed(github: ghapi.GitHub, path: str, repos: Repos) -> Iterator[Found]:
    # the stream with its first page read now, so the first pages read at once
    stream = _stream(github, path, repos)
    first = next(stream, None)
    return iter(()) if first is None else _chained(first, stream)


def labelled_path(repo: str, label: str) -> str:
    """The one listing of a label's open issues of a repository, oldest first (P9).

    Args:
        repo: ``owner/name``.
        label: the label.

    Returns:
        The path.
    """
    return f"repos/{repo}/issues?state=open&labels={label}&sort=created&direction=asc"


def _label_stream(
    github: ghapi.GitHub, settings: config.Config, label: str
) -> Iterator[Found]:
    # the open tickets of a label, oldest first: the first page of each
    # organisation's search at once, the others when the merge reaches them
    repos = orgsearch.configured(settings)
    firsts = concurrently.each(
        lambda org: _primed(
            github, orgsearch.path(org, "is:issue", f"label:{label}"), repos
        ),
        orgsearch.orgs(settings),
    )
    return heapq.merge(*firsts, key=lambda pair: pair[1].created_at)


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
    # the open tickets the owner ranks by this label, oldest first; read only when
    # the walk reaches the label (``tickets`` is lazy by label), at once, since the
    # order by age needs each one's creation (keyword: org-search)
    stated = sorted(
        reference
        for reference, named in settings.slots.owner_priorities.items()
        if named == label
    )
    found = concurrently.each(lambda each: ticketdata.open_ticket(github, each), stated)
    opened = [
        (reference, issue_of(reference, ticket))
        for reference, ticket in zip(stated, found)
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
        _label_stream(github, settings, label),
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

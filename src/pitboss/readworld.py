"""The one read of a command: the listings, then the items oldest first (keyword: one-path).

The owner: "You need to get *fewer issues*. Sort by age, stop when you get to 5
issues that aren't blocked." ``read_world`` reads every open pull request's listing
row (one call for each repository), then walks the order and examines an item (its
details and closure) only when the walk reaches it: the pull requests that are not
relock reviews, oldest first; then the tickets by priority label and age, a label's
first page of each repository merged by age and a later page read only when the
merge has used up the one before; then the relock pull requests. The walk stops
when it holds ``max(5, the slots configured)`` decisions; an item nobody acts on
counts for nothing, so the walk reads on past it. A blocker an examined item names
is examined in that item's place (keyword: dependency): the place a blocker takes is
the better of its own and its first namer's, so nothing the walk did not read can
move an item into or within the part it read.

What is known from the listings and the ledger alone is not read again: a ticket an
open pull request works on (keyword: taken), an item a slot holds, a ticket of a
repository under the owner's hold. Each is a ``Kept`` record. A read that fails
after its tries (``retrying``) fails the command: nothing is decided on a part.
"""

import dataclasses
import datetime
import heapq
import json
from typing import AbstractSet, Callable, Iterable, Iterator, Mapping, Sequence

from . import (
    blockedby,
    blockers,
    concurrently,
    config,
    configrepos,
    decide,
    finishpartial,
    ghapi,
    holdconfig,
    holds,
    issuelist,
    ledger,
    pullnames,
    pulls,
    relock,
    shapes,
    sharedred,
    stuckci,
    ticketdata,
    world,
)

STOP = 5  # the least number of decisions a walk stops at
LIMIT = blockedby.LIMIT  # the most blockers followed from one item


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """What the read starts from.

    Attributes:
        github: the API (its reads are tried again, then fail: ``retrying``).
        settings: the configuration.
        book: the slot ledger, as the live agents make it.
        free: how many slots are free now.
        holds: the owner's holds on new pull requests (``[holds]``).
        now: the time now.
        source: where a pull request of a repository is read from.
    """

    github: ghapi.GitHub
    settings: config.Config
    book: ledger.Ledger
    free: int
    holds: holdconfig.Holds
    now: datetime.datetime
    source: Callable[[config.Repo], pulls.Source]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Extent:
    """How much a command asks to be read.

    Attributes:
        named: the items examined whatever the walk reaches (the item the
            command names).
        every_pull: whether every open pull request is examined (the sweep).
    """

    named: Sequence[str]
    every_pull: bool


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


Candidate = world.Listed | Ticket


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class FullPage:
    """A page as long as a page can be: there may be one after it.

    Attributes:
        items: the page's raw items (none for a pull request).
    """

    items: Sequence[shapes.Issue | None]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class LastPage:
    """A page shorter than a page can be: the list ends with it.

    Attributes:
        items: the page's raw items (none for a pull request).
    """

    items: Sequence[shapes.Issue | None]


Page = FullPage | LastPage


def stop_count(book: ledger.Ledger) -> int:
    """The number of decisions a walk stops at: ``max(5, the slots configured)``.

    Args:
        book: the ledger, one row for each slot.

    Returns:
        The count.
    """
    return max(STOP, len(book.slots))


def listed_row(
    repo: config.Repo, prefix: str, row: Mapping[str, object]
) -> world.Listed:
    """One open pull request as its listing row gives it.

    Args:
        repo: its repository.
        prefix: the relock branch prefix.
        row: the row of ``pulls?state=open``.

    Returns:
        The row.
    """
    number = int(str(row["number"]))
    head = row["head"]
    branch = str(head["ref"]) if isinstance(head, dict) else ""
    title, body = str(row.get("title") or ""), str(row.get("body") or "")
    return world.Listed(
        reference=f"{repo.slug}#{number}",
        repo=repo,
        number=number,
        title=title,
        body=body,
        branch=branch,
        draft=bool(row.get("draft")),
        created_at=str(row["created_at"]),
        relock=relock.is_relock(branch, prefix),
        works_on=pullnames.names(title, body, branch, repo),
    )


def _rows(text: str) -> Sequence[Mapping[str, object]]:
    found = json.loads(text)
    return [each for each in found if isinstance(each, dict)]


def listing(github: ghapi.GitHub, settings: config.Config) -> Sequence[world.Listed]:
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
    rows = [listed_row(repo, prefix, row) for repo, got in zip(repos, pages) for row in got]
    return sorted(rows, key=lambda each: each.created_at)


def _page(github: ghapi.GitHub, path: str, number: int) -> Page:
    items = issuelist.listed(
        ghapi.get(github, f"{path}&per_page={ghapi.PAGE_SIZE}&page={number}")
    )
    return FullPage(items=items) if len(items) == ghapi.PAGE_SIZE else LastPage(items=items)


def _stream(github: ghapi.GitHub, path: str) -> Iterator[shapes.Issue]:
    # a page is raw items (the list holds pull requests): a full one may have more
    number = 1
    while True:
        page = _page(github, path, number)
        yield from filter(None, page.items)
        if isinstance(page, LastPage):
            return
        number += 1


def _label_stream(
    github: ghapi.GitHub, repos: Sequence[config.Repo], label: str
) -> Iterator[tuple[str, shapes.Issue]]:
    # the open tickets of a label, oldest first, across repositories: the first
    # page of every repository at once, the others when the merge reaches them
    query = f"issues?state=open&labels={label}&sort=created&direction=asc"
    firsts = concurrently.each(
        lambda repo: _primed(github, f"repos/{repo.slug}/{query}"), repos
    )
    streams = [
        ((f"{repo.slug}#{each.number}", each) for each in first)
        for repo, first in zip(repos, firsts)
    ]
    return heapq.merge(*streams, key=lambda pair: pair[1].created_at)


def _primed(github: ghapi.GitHub, path: str) -> Iterator[shapes.Issue]:
    # the stream with its first page read now, so the first pages read at once
    stream = _stream(github, path)
    first = next(stream, None)
    return iter(()) if first is None else _chained(first, stream)


def _chained(first: shapes.Issue, rest: Iterator[shapes.Issue]) -> Iterator[shapes.Issue]:
    yield first
    yield from rest


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
    tickets = [
        (reference, _issue_of(reference, ticket))
        for reference, ticket in found
        if ticket is not None and not ticket.pull
    ]
    return iter(sorted(tickets, key=lambda pair: pair[1].created_at))


def _issue_of(reference: str, ticket: ticketdata.Ticket) -> shapes.Issue:
    return shapes.Issue(
        number=int(reference.rpartition("#")[2]),
        title=ticket.title,
        created_at=ticket.created_at,
        labels=ticket.labels,
        body=ticket.body,
        comments=ticket.comments,
    )


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
    repos = configrepos.repositories(settings)
    stated = settings.slots.owner_priorities
    seen: set[str] = set()
    for priority, label in enumerate(settings.slots.priority_labels):
        merged = heapq.merge(
            _label_stream(github, repos, label),
            _owner_stated(github, settings, label),
            key=lambda pair: pair[1].created_at,
        )
        for reference, issue in merged:
            ranked = stated.get(reference, label) == label
            if ranked and reference not in seen:
                seen.add(reference)
                yield Ticket(reference=reference, issue=issue, priority=priority)


def candidates(
    github: ghapi.GitHub, settings: config.Config, rows: Sequence[world.Listed]
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


def _held(book: ledger.Ledger) -> AbstractSet[str]:
    return frozenset(slot.task for slot in book.slots if slot.agent)


def _blockers_of(
    github: ghapi.GitHub, settings: config.Config, facts: pulls.PullFacts
) -> Sequence[str]:
    # the open items a pull request waits for: its own Blocked-by lines, and the
    # blockers of the tickets it fixes (keyword: blocked-pull)
    me = pulls.reference(facts)
    declared = [
        each
        for each in blockedby.declared(facts)
        if blockedby.read(github, each).state is blockedby.State.OPEN
    ]
    named = pullnames.names(
        facts.pull.title, facts.pull.body, facts.pull.head.branch, facts.repo
    )
    waits = [blockers.pull_waits(github, settings, facts, each) for each in sorted(named)]
    found = [*declared, *(b for w in waits if w is not None for b in w.blockers)]
    return [each for each in dict.fromkeys(found) if each != me]


def examine_pull(reading: Reading, row: world.Listed) -> world.Record:
    """Read one open pull request and its closure.

    Args:
        reading: what the read starts from.
        row: its listing row.

    Returns:
        Its record; a pull request a slot holds is kept, not read.
    """
    if row.reference in _held(reading.book):
        return world.Kept(reference=row.reference, by=world.Keeper.SLOT)
    github = reading.github
    facts = pulls.fetch(reading.source(row.repo), row.repo, row.number)
    blocked = blockedby.settle(github, [facts])[0]
    shared = sharedred.settle(github, blocked)[0]
    settled = pulls.readable(finishpartial.settle(shared)[0])[0]
    found = _blockers_of(github, reading.settings, settled)
    stuck = stuckci.lines(github, [settled], reading.now)  # keyword: stuck-ci
    return world.PullRecord(listed=row, facts=settled, blockers=found, stuck=stuck)


def examine_ticket(reading: Reading, ticket: Ticket, taken: AbstractSet[str]) -> world.Record:
    """Read one open ticket's closure.

    Args:
        reading: what the read starts from.
        ticket: the ticket.
        taken: the tickets an open pull request works on.

    Returns:
        Its record; a ticket the listings or the ledger already decide is kept.
    """
    reference = ticket.reference
    settings = reading.settings
    if reference in _held(reading.book):
        return world.Kept(reference=reference, by=world.Keeper.SLOT)
    if reference in taken:
        return world.Kept(reference=reference, by=world.Keeper.PULL)
    found, superseded = blockers.waiting(reading.github, settings, ticket.issue, reference)
    slug = reference.rpartition("#")[0]
    project = settings.project
    return world.TicketRecord(
        reference=reference,
        issue=ticket.issue,
        priority=ticket.priority,
        superseded=superseded,
        blockers=found,
        opens_ready=not project.drafts or slug in project.no_drafts,
    )


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _Walking:
    # what one walk knows: the read's start, the listing, and what is taken
    reading: Reading
    rows: Mapping[str, world.Listed]
    taken: AbstractSet[str]
    held_repos: AbstractSet[str]


def _examine(walking: _Walking, candidate: Candidate) -> world.Record:
    match candidate:
        case world.Listed():
            return examine_pull(walking.reading, candidate)
        case Ticket():
            slug = candidate.reference.rpartition("#")[0]
            if slug in walking.held_repos and candidate.reference not in walking.taken:
                return world.Kept(reference=candidate.reference, by=world.Keeper.HOLD)
            return examine_ticket(walking.reading, candidate, walking.taken)


def _by_reference(walking: _Walking, reference: str) -> Candidate | None:
    # an item named as a blocker: an open pull request of the listing, else a ticket
    row = walking.rows.get(reference)
    if row is not None:
        return row
    found = ticketdata.open_ticket(walking.reading.github, reference)
    if found is None or found.pull:
        return None
    labels = walking.reading.settings.slots.priority_labels
    having = [at for at, label in enumerate(labels) if label in found.labels]
    return Ticket(
        reference=reference,
        issue=_issue_of(reference, found),
        priority=min(having, default=len(labels)),
    )


def _with_blockers(
    walking: _Walking, candidate: Candidate, seen: set[str]
) -> Iterator[world.Record]:
    # the item, then each open blocker it names, examined in its place
    todo = [candidate]
    followed = 0
    while todo and followed <= LIMIT:
        each = todo.pop(0)
        reference = each.reference
        if reference in seen:
            continue
        seen.add(reference)
        followed += 1
        record = _examine(walking, each)
        yield record
        if decide.decide_item(record) is None:
            named = (_by_reference(walking, b) for b in world.blockers_of(record))
            todo.extend(found for found in named if found is not None)


def walk(walking: _Walking, order: Iterable[Candidate], stop: int, every_pull: bool) -> world.Walk:
    """Examine the order until it holds ``stop`` decisions.

    Args:
        walking: what the walk knows.
        order: the candidates, first to take first.
        stop: the number of decisions the walk stops at.
        every_pull: whether every open pull request is examined (the sweep).

    Returns:
        ``Stopped`` when the decisions reached the stop, ``Exhausted`` when the
        order ended first (every list read to its last page).
    """
    examined: list[world.Record] = []
    seen: set[str] = set()
    decisions: list[decide.Decision] = []
    for candidate in order:
        pulls_left = every_pull and isinstance(candidate, world.Listed)
        if len(decisions) >= stop and not pulls_left:
            return world.Stopped(examined=examined)
        for record in _with_blockers(walking, candidate, seen):
            examined.append(record)
            found = decide.decide_item(record)
            if found is not None:
                decisions.append(found)
    return world.Exhausted(examined=examined)


def _named(walking: _Walking, references: Sequence[str]) -> Sequence[world.Record]:
    found = [_by_reference(walking, each) for each in references]
    return [_examine(walking, each) for each in found if each is not None]


def read_world(reading: Reading, extent: Extent) -> world.World:
    """Read what a command decides from: once, and no more than the answer needs.

    Args:
        reading: what the read starts from.
        extent: how much the command asks to be read.

    Returns:
        The world.
    """
    settings = reading.settings
    rows = listing(reading.github, settings)
    taken = frozenset().union(*(each.works_on for each in rows))
    held_repos = holds.standing(reading.holds, [each.repo.slug for each in rows])
    walking = _Walking(
        reading=reading,
        rows={each.reference: each for each in rows},
        taken=taken,
        held_repos=frozenset(held_repos),
    )
    stop = stop_count(reading.book)
    order = candidates(reading.github, settings, rows)
    return world.World(
        listing=rows,
        walk=walk(walking, order, stop, extent.every_pull),
        named=_named(walking, extent.named),
        book=reading.book,
        free=reading.free,
        stop=stop,
    )

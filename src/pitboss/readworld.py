"""The one read of a command: the listings, then items oldest first (one-path).

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
from typing import AbstractSet, Callable, Iterable, Iterator, Mapping, Sequence

from . import (
    answer,
    blockedby,
    blockers,
    config,
    ghapi,
    holdconfig,
    holds,
    ledger,
    listed,
    pullnames,
    pulls,
    stuckci,
    ticketdata,
    workorder,
    world,
)

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
        settle: a pull request's step settled by its blockers, its shared red and
            its hand-back (``blockedby``, ``sharedred``, ``finishpartial``).
        decide_item: the one decider of an item (``decide.decide_item``), which the
            walk counts its stop with.
    """

    github: ghapi.GitHub
    settings: config.Config
    book: ledger.Ledger
    free: int
    holds: holdconfig.Holds
    now: datetime.datetime
    source: Callable[[config.Repo], pulls.Source]
    settle: Callable[[pulls.PullFacts], pulls.PullFacts]
    decide_item: Callable[[world.Record], answer.Decision | None]


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
    waits = [
        blockers.pull_waits(github, settings, facts, each) for each in sorted(named)
    ]
    found = [*declared, *(b for w in waits if w is not None for b in w.blockers)]
    return [each for each in dict.fromkeys(found) if each != me]


def examine_pull(reading: Reading, row: listed.Listed) -> world.Record:
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
    fetched = pulls.fetch(reading.source(row.repo), row.repo, row.number)
    settled = reading.settle(fetched)
    found = _blockers_of(github, reading.settings, settled)
    stuck = stuckci.lines(github, [settled], reading.now)  # keyword: stuck-ci
    return world.PullRecord(row=row, facts=settled, blockers=found, stuck=stuck)


def examine_ticket(
    reading: Reading, ticket: workorder.Ticket, taken: AbstractSet[str]
) -> world.Record:
    """Read one open ticket's closure.

    Args:
        reading: what the read starts from.
        ticket: the ticket.
        taken: the tickets an open pull request works on.

    Returns:
        Its record; a ticket the listings or the ledger already decide is kept.
    """
    reference = ticket.reference
    kept = _kept(reading.book, reference, taken)
    if kept is not None:
        return kept
    found, superseded = blockers.waiting(
        reading.github, reading.settings, ticket.issue, reference
    )
    return world.TicketRecord(
        reference=reference,
        issue=ticket.issue,
        priority=ticket.priority,
        superseded=superseded,
        blockers=found,
        opens_ready=_opens_ready(reading.settings.project, reference),
    )


def _kept(
    book: ledger.Ledger, reference: str, taken: AbstractSet[str]
) -> world.Kept | None:
    # a ticket the ledger or the listings already decide, with no read of it
    if reference in _held(book):
        return world.Kept(reference=reference, by=world.Keeper.SLOT)
    if reference in taken:
        return world.Kept(reference=reference, by=world.Keeper.PULL)
    return None


def _opens_ready(project: config.Project, reference: str) -> bool:
    # keyword: no-drafts
    return not project.drafts or reference.rpartition("#")[0] in project.no_drafts


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _Walking:
    # what one walk knows: the read's start, the listing, and what is taken
    reading: Reading
    rows: Mapping[str, listed.Listed]
    taken: AbstractSet[str]
    held_repos: AbstractSet[str]
    stop: int


def _examine(walking: _Walking, candidate: workorder.Candidate) -> world.Record:
    match candidate:
        case listed.Listed():
            return examine_pull(walking.reading, candidate)
        case workorder.Ticket():
            slug = candidate.reference.rpartition("#")[0]
            if slug in walking.held_repos and candidate.reference not in walking.taken:
                return world.Kept(reference=candidate.reference, by=world.Keeper.HOLD)
            return examine_ticket(walking.reading, candidate, walking.taken)


def _by_reference(walking: _Walking, reference: str) -> workorder.Candidate | None:
    # an item named as a blocker: an open pull request of the listing, else a ticket
    row = walking.rows.get(reference)
    if row is not None:
        return row
    found = ticketdata.open_ticket(walking.reading.github, reference)
    if found is None or found.pull:
        return None
    labels = walking.reading.settings.slots.priority_labels
    having = [at for at, label in enumerate(labels) if label in found.labels]
    return workorder.Ticket(
        reference=reference,
        issue=workorder.issue_of(reference, found),
        priority=min(having, default=len(labels)),
    )


def _with_blockers(
    walking: _Walking, candidate: workorder.Candidate, seen: set[str]
) -> Iterator[world.Record]:
    # the item, then each open blocker it names, examined in its place
    todo = [candidate]
    followed = 0
    while todo and followed <= LIMIT:
        each = todo.pop(0)
        if each.reference in seen:
            continue
        seen.add(each.reference)
        followed += 1
        record = _examine(walking, each)
        yield record
        if walking.reading.decide_item(record) is None:
            named = (_by_reference(walking, b) for b in world.blockers_of(record))
            todo.extend(found for found in named if found is not None)


def walk(
    walking: _Walking, order: Iterable[workorder.Candidate], every_pull: bool
) -> world.Walk:
    """Examine the order until it holds the stop count of decisions.

    Args:
        walking: what the walk knows.
        order: the candidates, first to take first.
        every_pull: whether every open pull request is examined (the sweep).

    Returns:
        ``Stopped`` when the decisions reached the stop, ``Exhausted`` when the
        order ended first (every list read to its last page).
    """
    examined: list[world.Record] = []
    seen: set[str] = set()
    decisions: list[answer.Decision] = []
    for candidate in order:
        pulls_left = every_pull and isinstance(candidate, listed.Listed)
        if len(decisions) >= walking.stop and not pulls_left:
            return world.Stopped(examined=examined, stop=walking.stop)
        for record in _with_blockers(walking, candidate, seen):
            examined.append(record)
            found = walking.reading.decide_item(record)
            decisions.extend([found] if found is not None else [])
    return world.Exhausted(examined=examined)


def _named(walking: _Walking, references: Sequence[str]) -> Sequence[world.Record]:
    found = [_by_reference(walking, each) for each in references]
    return [_examine(walking, each) for each in found if each is not None]


def _start(reading: Reading, rows: Sequence[listed.Listed]) -> _Walking:
    slugs = [each.repo.slug for each in rows]
    return _Walking(
        reading=reading,
        rows={each.reference: each for each in rows},
        taken=frozenset().union(*(each.works_on for each in rows)),
        held_repos=frozenset(holds.standing(reading.holds, slugs)),
        stop=workorder.stop_count(reading.book),
    )


def read_world(reading: Reading, extent: Extent) -> world.World:
    """Read what a command decides from: once, and no more than the answer needs.

    Args:
        reading: what the read starts from.
        extent: how much the command asks to be read.

    Returns:
        The world.
    """
    rows = workorder.listing(reading.github, reading.settings)
    walking = _start(reading, rows)
    order = workorder.candidates(reading.github, reading.settings, rows)
    return world.World(
        listing=rows,
        walk=walk(walking, order, extent.every_pull),
        named=_named(walking, extent.named),
        book=reading.book,
        free=reading.free,
    )

"""The one read of a command: the listings, then items oldest first (one-path).

The owner: "You need to get *fewer issues*. Sort by age, stop when you get to 5
issues that aren't blocked." ``read_world`` reads every open pull request's listing
row (one call for each repository), then walks the order and examines an item (its
details and closure) only when the walk reaches it: the pull requests that are not
relock reviews, oldest first; then the tickets by priority label and age, a label's
first page of each repository merged by age and a later page read only when the
merge has used up the one before; then the relock pull requests. The walk stops
when it holds ``max(5, the slots configured)`` decisions; an item no actor takes
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
import enum
from typing import AbstractSet, Callable, Iterable, Iterator, Mapping, Sequence

from . import (
    allowlistmiss,
    answer,
    blockedby,
    blockedstep,
    blockers,
    config,
    failures,
    flowstep,
    ghapi,
    holdconfig,
    holds,
    ledger,
    listed,
    pullnames,
    pulls,
    readextent,
    steps,
    stuckci,
    ticketdata,
    workorder,
    world,
)

LIMIT = blockedby.LIMIT  # the most blockers followed from one item
GATED = frozenset({steps.Step.MERGE, steps.Step.UNDRAFT})  # keyword: gate


PullReader = world.PullReader


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """What the read starts from.

    Attributes:
        github: the API (its reads are tried again, then fail: ``retrying``).
        settings: the configuration.
        book: the slot ledger, as the live agents make it.
        holds: the owner's holds on new pull requests (``[holds]``).
        now: the time now.
        pull: a pull request read (``decide.facts_of`` gives its step from what
            was read and the closure ``examine_pull`` reads).
        decide_item: the one decider of an item (``decide.decide_item``), which the
            walk counts its stop with.
        closures: how a pull request's gate and shared red are read.
        quiesced: whether the owner quiesced the work (``quiesce``): no ticket
            starts, so each is kept as held.
        released: the ledger less the slots whose worker handed back the head
            the listing gives (``handedback``, keyword: hand-back-done).
    """

    github: ghapi.GitHub
    settings: config.Config
    book: ledger.Ledger
    holds: holdconfig.Holds
    now: datetime.datetime
    pull: PullReader
    decide_item: Callable[[world.Record], answer.Decision | None]
    closures: world.Closures
    quiesced: bool
    released: Callable[[Sequence[listed.Listed], ledger.Ledger], ledger.Ledger]


def _held(book: ledger.Ledger) -> AbstractSet[str]:
    return frozenset(slot.task for slot in book.slots if slot.agent)


def _blockers_of(
    github: ghapi.GitHub,
    settings: config.Config,
    facts: pulls.PullFacts,
    closure: blockedstep.Closure,
) -> Sequence[str]:
    # the open items a pull request waits for: its own Blocked-by lines, and the
    # blockers of the tickets it fixes (keyword: blocked-pull)
    me = pulls.reference(facts)
    open_ones = [each for each in closure.found if each.state is blockedstep.State.OPEN]
    declared = [each.reference for each in open_ones]
    named = pullnames.names(
        facts.pull.title, facts.pull.body, facts.pull.head.branch, facts.repo
    )
    waits = {
        each: blockers.pull_waits(github, settings, facts, each)
        for each in sorted(named)
    }
    found = [
        *declared,
        *(b for w in waits.values() if w is not None for b in w.blockers),
    ]
    for ticket in (each for each, w in waits.items() if w is not None):
        refused = blockers.refusal_blockers(github, settings, me, ticket)
        # a ticket the PR works on never blocks it (keyword: plan-refusal)
        found += [each for each in refused if each not in waits]
        found += _allowlist(github, facts)
    return [each for each in dict.fromkeys(found) if each != me]


def _fixing(facts: pulls.PullFacts) -> bool:
    # whether the pull request's step is a fix of its CI
    step = facts.step
    return isinstance(step, steps.Next) and step.task is steps.Task.FIX_CI


def _allowlist(github: ghapi.GitHub, facts: pulls.PullFacts) -> Sequence[str]:
    # keyword: allowlist-miss (pitboss#448): a red only a merged allowlist line fixes
    return allowlistmiss.missing(github, facts)[1] if _fixing(facts) else ()


def examine_pull(
    reading: Reading, row: listed.Listed, others: Sequence[listed.Listed]
) -> world.PullRecord:
    """Read one open pull request and its closure.

    Args:
        reading: what the read starts from.
        row: its listing row.
        others: the other open rows of its repository (a shared red's closure).

    Returns:
        Its record, which says whether a slot holds it.
    """
    held = row.reference in _held(reading.book)
    github = reading.github
    read = reading.pull(row)
    facts = flowstep.at_flow(read)  # the flow's step chooses the closures read
    blocked_by = blockedby.read_closure(github, facts)
    stuck = stuckci.lines(github, [facts], reading.now)  # keyword: stuck-ci
    gated = reading.closures.gated(facts) if steps.step_is(facts.step, GATED) else None
    return world.PullRecord(
        row=row,
        facts=read,
        blocked_by=blocked_by,
        shared=reading.closures.shared(facts, others),
        blockers=_blockers_of(github, reading.settings, facts, blocked_by),
        stuck=stuck,
        gated=gated,
        held=held,
        failures=failures.read_all(github, facts) if _fixing(facts) else {},
    )


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
    every_pull: bool


def _kept_by(walking: _Walking, candidate: workorder.Candidate) -> world.Kept | None:
    # an item the ledger, a hold or the quiesce already decides, with no read of it
    reference = candidate.reference
    if isinstance(candidate, listed.Listed):  # a PR a slot holds; the sweep reads it
        held = reference in _held(walking.reading.book) and not walking.every_pull
        by = world.Keeper.SLOT
    else:  # a ticket
        slug = reference.rpartition("#")[0]
        holding = slug in walking.held_repos or walking.reading.quiesced
        held = holding and reference not in walking.taken
        by = world.Keeper.HOLD
    return world.Kept(reference=reference, by=by) if held else None


def _examine(walking: _Walking, candidate: workorder.Candidate) -> world.Record:
    kept = _kept_by(walking, candidate)
    if kept is not None:
        return kept
    if isinstance(candidate, workorder.Ticket):
        return examine_ticket(walking.reading, candidate, walking.taken)
    rows = walking.rows.values()
    others = [each for each in rows if each.repo == candidate.repo]
    others = [each for each in others if each != candidate]
    return examine_pull(walking.reading, candidate, others)


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


def _decisions(
    walking: _Walking, records: Sequence[world.Record]
) -> Sequence[answer.Decision]:
    # the decisions of the records, which the stop counts
    decide_item = walking.reading.decide_item
    return [found for each in records if (found := decide_item(each)) is not None]


class Go(enum.Enum):
    """What the walk does with the next candidate.

    Attributes:
        TAKE: examine it.
        SKIP: pass it (a ticket past the stop, in the sweep).
        STOP: end the walk.
    """

    TAKE = enum.auto()
    SKIP = enum.auto()
    STOP = enum.auto()


def _past(walking: _Walking, candidate: workorder.Candidate) -> Go:
    # past the stop, only the sweep goes on, and only to its pull requests
    if not walking.every_pull:
        return Go.STOP
    return Go.TAKE if isinstance(candidate, listed.Listed) else Go.SKIP


def walk(walking: _Walking, order: Iterable[workorder.Candidate]) -> world.Walk:
    """Examine the order until it holds the stop count of decisions.

    The sweep reads every open pull request: past the stop it skips the tickets
    and examines the pull requests left.

    Args:
        walking: what the walk knows.
        order: the candidates, first to take first.

    Returns:
        ``Stopped`` when the decisions reached the stop, ``Exhausted`` when the
        order ended first (every list read to its last page).
    """
    examined: list[world.Record] = []
    seen: set[str] = set()
    decisions: list[answer.Decision] = []
    for candidate in order:
        go = _past(walking, candidate) if len(decisions) >= walking.stop else Go.TAKE
        if go is Go.STOP:
            break
        if go is Go.TAKE:
            records = list(_with_blockers(walking, candidate, seen))
            examined.extend(records)
            decisions.extend(_decisions(walking, records))
    if len(decisions) >= walking.stop:
        return world.Stopped(examined=examined, stop=walking.stop)
    return world.Exhausted(examined=examined)


def _named(walking: _Walking, references: Sequence[str]) -> Sequence[world.Record]:
    found = [_by_reference(walking, each) for each in references]
    return [_examine(walking, each) for each in found if each is not None]


def _start(
    reading: Reading, rows: Sequence[listed.Listed], every_pull: bool
) -> _Walking:
    slugs = [each.repo.slug for each in rows]
    return _Walking(
        reading=reading,
        rows={each.reference: each for each in rows},
        taken=frozenset().union(*(each.works_on for each in rows)),
        held_repos=frozenset(holds.standing(reading.holds, slugs)),
        stop=workorder.stop_count(reading.book),
        every_pull=every_pull,
    )


def read_world(reading: Reading, extent: readextent.Extent) -> world.World:
    """Read what a command decides from: once, and no more than the answer needs.

    Args:
        reading: what the read starts from.
        extent: how much the command asks to be read.

    Returns:
        The world.
    """
    rows = workorder.listing(reading.github, reading.settings)
    reading = dataclasses.replace(reading, book=reading.released(rows, reading.book))
    walking = _start(reading, rows, extent.every_pull)
    order = workorder.candidates(reading.github, reading.settings, rows)
    named = [
        *extent.named,
        *readextent.pushed(reading.github.run, extent, rows),
        *reading.settings.slots.owner_priorities,
    ]
    return world.World(
        listing=rows,
        walk=walk(walking, order),
        named=_named(walking, list(dict.fromkeys(named))),
        book=reading.book,
        free=sum(1 for slot in reading.book.slots if not slot.agent),
    )

"""The one read of a command: the listings, then items oldest first (one-path).

The owner: "You need to get *fewer issues*. Sort by age, stop when you get to 5
issues that aren't blocked." ``read_world`` reads the first page of each
organisation's searches of open pull requests (``pullsearch``), then walks the
order and examines an item (its details and closure, read by ``examine``, which
``onepath`` hands it as the ``Examiner``) only when the walk reaches it: the pull
requests that are not relock reviews, oldest first; then the tickets by priority
label and age; then the relock pull requests. A later page
of a listing is read only when the walk reaches the end of the one before. The walk
takes its next items from ``placing.order`` alone, in waves: each wave is as many
items as decisions are still wanted, examined at once (plan 3.1, 6.3 P10), and it
stops when it holds ``max(5, the slots configured)`` decisions; an item no actor
takes counts for nothing, so the walk reads on past it. A blocker an examined item
names takes that item's place (keyword: dependency).

An item ``decide`` already says no actor takes from the grounds alone (a slot holds
it, a pull request works on it, a hold covers its repository) is not read: it is an
``Occupied`` record, and ``decide`` decides it. A read that fails after its tries
(``retrying``) fails the command: nothing is decided on a part.
"""

import dataclasses
from typing import Callable, Iterator, Mapping, Sequence

from . import (
    actfacts,
    answer,
    blockedby,
    branchtaken,
    concurrently,
    config,
    configrepos,
    ghapi,
    holdconfig,
    holdissues,
    holdparse,
    ledger,
    listed,
    placing,
    pullrecords,
    pullsearch,
    readextent,
    ticketdata,
    workorder,
    world,
)

LIMIT = blockedby.LIMIT  # the most blockers followed from one item
PullReader = world.PullReader
Decides = Callable[[world.Grounds, world.Record], answer.Decision | None]
Kept = Callable[[world.Grounds, str], bool]
Others = Sequence[listed.Listed]  # the other open rows of a pull request's repository
Holds = Sequence[pullrecords.Hold]  # the hold issues of a pull request's repository
Acts = Callable[[], actfacts.ActRead]  # what an act verb is decided from, read


def no_acts() -> actfacts.ActRead:
    """The read of a command that asks for no act verb.

    Returns:
        ``actfacts.NO_ACT``.
    """
    return actfacts.NO_ACT


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Judge:
    """What the walk asks ``decide`` (the reader only reads, plan 6.1).

    Attributes:
        decides: the one decider of an item on its grounds (``decide.decide_in``),
            which the walk counts its stop with.
        pull_kept: whether the grounds alone say no actor takes a pull request
            (``decide.pull_kept``), so it is not read.
        ticket_kept: the same for a ticket (``decide.ticket_kept``).
    """

    decides: Decides
    pull_kept: Kept
    ticket_kept: Kept


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Examiner:
    """How an item is read when the walk reaches it (``examine``).

    Attributes:
        pull: an open pull request and its closure, given the other open rows of
            its repository and its repository's holds (keyword: gate).
        ticket: an open ticket's closure, given its repository's open branches.
    """

    pull: Callable[[listed.Listed, Others, Holds], world.PullRecord]
    ticket: Callable[[workorder.Ticket, Sequence[str]], world.TicketRecord]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """What the read starts from.

    Attributes:
        github: the API (its reads are tried again, then fail: ``retrying``).
        settings: the configuration.
        book: the slot ledger, as the live agents make it.
        holds: the owner's holds on new pull requests (``[holds]``).
        quiesced: whether the owner quiesced the work (``quiesce``).
        judge: what the walk asks ``decide``.
        examiner: how an item is read.
        released: the ledger less the slots whose worker handed back the head
            the listing gives (``handedback``, keyword: hand-back-done).
        acts: what the act verb the command asks for is decided from
            (``actread``; ``actfacts.NO_ACT`` for any other command).
    """

    github: ghapi.GitHub
    settings: config.Config
    book: ledger.Ledger
    holds: holdconfig.Holds
    quiesced: bool
    judge: Judge
    examiner: Examiner
    released: Callable[[Sequence[listed.Listed], ledger.Ledger], ledger.Ledger]
    acts: Acts


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _Walking:
    # what one walk knows: the read's start, the pull requests read, the stop
    reading: Reading
    read: pullsearch.Pulls
    stop: int
    every_pull: bool
    branches: dict[str, Sequence[str]]  # each repository's open branches, read once
    held: holdparse.Held  # each repository's hold issues, read once


def _rows(walking: _Walking) -> Mapping[str, listed.Listed]:
    # every open pull request read so far, by its reference
    return {each.reference: each for each in walking.read.read}


def _grounds(walking: _Walking) -> world.Grounds:
    # what is known before an item is read, with every row read so far
    reading = walking.reading
    rank = pullsearch.ranked(reading.settings)
    rows = sorted(
        _rows(walking).values(), key=lambda row: (row.created_at, rank[row.repo.slug])
    )
    return world.Grounds(
        listing=rows,
        book=reading.book,
        holds=reading.holds,
        held=walking.held,
        quiesced=reading.quiesced,
    )


def _occupied(walking: _Walking, candidate: workorder.Candidate) -> bool:
    # an item the grounds already decide is not read; the sweep reads every PR
    judge = walking.reading.judge
    if isinstance(candidate, workorder.Ticket):
        return judge.ticket_kept(_grounds(walking), candidate.reference)
    swept = walking.every_pull
    return not swept and judge.pull_kept(_grounds(walking), candidate.reference)


def _examine(walking: _Walking, candidate: workorder.Candidate) -> world.Record:
    # the item's record, read
    if isinstance(candidate, workorder.Ticket):
        branches = walking.branches[configrepos.repo_of(candidate.reference).slug]
        return walking.reading.examiner.ticket(candidate, branches)
    rows = walking.read.read
    others = [each for each in rows if each.repo == candidate.repo]
    others = [each for each in others if each != candidate]
    holds = walking.held.get(candidate.repo.slug, ())
    return walking.reading.examiner.pull(candidate, others, holds)


def _by_reference(walking: _Walking, reference: str) -> workorder.Candidate | None:
    # an item named as a blocker: an open pull request read, else a ticket
    rows = _rows(walking)
    if reference in rows:
        return rows[reference]
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


def _stream(walking: _Walking) -> Iterator[workorder.Candidate]:
    # the order of the listings: the pull requests, the tickets, the relock
    # reviews; the relock reviews are read before the tickets, so the grounds of
    # a ticket hold every open pull request (keyword: relock-last, taken)
    reading = walking.reading
    yield from walking.read.pulls
    relocks = list(walking.read.relocks)
    yield from workorder.tickets(reading.github, reading.settings)
    yield from relocks


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _Walked:
    # what the walk holds: the candidates listed in order, what was examined and
    # the names each examined item gave, and the decisions
    listed: dict[str, workorder.Candidate]
    examined: dict[str, world.Record]
    named: list[tuple[str, Sequence[str]]]
    depth: dict[str, int]
    decisions: list[answer.Decision]


def _wave(
    walking: _Walking,
    stream: Iterator[workorder.Candidate],
    walked: _Walked,
    wanted: int,
) -> Sequence[workorder.Candidate]:
    # the next items of ``placing.order`` not yet examined, as many as wanted,
    # listing more of the order when it runs short
    fresh = _fresh(walked)
    if len(fresh) < wanted:
        for more in stream:
            walked.listed.setdefault(more.reference, more)
            fresh = _fresh(walked)
            if len(fresh) >= wanted:
                break
    taken = fresh[:wanted]
    unlisted = [each for each in taken if each not in walked.listed]
    read = concurrently.each(lambda each: _by_reference(walking, each), unlisted)
    found = {**dict(zip(unlisted, read)), **walked.listed}  # the blockers at once
    resolved = [_resolved(walked, each, found.get(each)) for each in taken]
    return [each for each in resolved if each is not None]


def _fresh(walked: _Walked) -> Sequence[str]:
    # the order's references not yet examined
    placed = placing.order(list(walked.listed), walked.named)
    return [each for each in placed if each not in walked.examined]


def _resolved(
    walked: _Walked, reference: str, found: workorder.Candidate | None
) -> workorder.Candidate | None:
    # a candidate listed, or a blocker read by its reference
    if found is None:  # a blocker that is no open item: nothing to examine
        walked.examined[reference] = world.Occupied(reference=reference, pull=False)
    return found


def _took(walking: _Walking, walked: _Walked, wave: Mapping[str, world.Record]) -> None:
    # each record of a wave: its decision, or the blockers it names
    for reference, item in wave.items():
        walked.examined[reference] = item
        found = walking.reading.judge.decides(_grounds(walking), item)
        if found is not None:
            walked.decisions.append(found)
        depth = walked.depth.get(reference, 0)
        names = world.blockers_of(item) if found is None and depth < LIMIT else ()
        for each in names:
            walked.depth.setdefault(each, depth + 1)
        walked.named.append((reference, names))


def walk(walking: _Walking) -> world.Walk:
    """Examine the order, a wave at a time, until it holds the stop count of decisions.

    The sweep reads every open pull request: past the stop it examines the pull
    requests left, and no ticket.

    Args:
        walking: what the walk knows.

    Returns:
        ``Stopped`` when the decisions reached the stop, ``Exhausted`` when the
        order ended first (every list read to its last page).
    """
    stream = _stream(walking)
    walked = _Walked(listed={}, examined={}, named=[], depth={}, decisions=[])
    decisions: list[answer.Decision] = walked.decisions
    while not len(decisions) >= walking.stop:
        wave = _wave(walking, stream, walked, walking.stop - len(decisions))
        if not wave:
            break
        _took(walking, walked, _each(walking, wave))
    if walking.every_pull:
        _swept(walking, walked)
    placed = placing.order(list(walked.listed), walked.named)
    ordered = [walked.examined[each] for each in placed if each in walked.examined]
    if len(decisions) >= walking.stop:
        return world.Stopped(examined=ordered, stop=walking.stop)
    return world.Exhausted(examined=ordered)


def _swept(walking: _Walking, walked: _Walked) -> None:
    # the sweep reads every open pull request: those the walk did not reach
    rest = [*walking.read.pulls, *walking.read.relocks, *walking.read.read]
    for each in rest:
        walked.listed.setdefault(each.reference, each)
    left = {each.reference: each for each in rest}
    wave = [each for ref, each in left.items() if ref not in walked.examined]
    _took(walking, walked, _each(walking, wave))


def _each(
    walking: _Walking, wave: Sequence[workorder.Candidate]
) -> Mapping[str, world.Record]:
    # one wave, examined at once (plan 3.1: one wave of workers); the open
    # branches of a ticket's repository are read once a walk (keyword: taken)
    occupied = {
        each.reference: world.Occupied(
            reference=each.reference, pull=isinstance(each, listed.Listed)
        )
        for each in wave
        if _occupied(walking, each)
    }
    read = [each for each in wave if each.reference not in occupied]
    slugs = {
        configrepos.repo_of(each.reference).slug
        for each in read
        if isinstance(each, workorder.Ticket)
    }
    wanted = sorted(slugs - set(walking.branches))
    github = walking.reading.github
    found = concurrently.each(lambda slug: branchtaken.branches(github, slug), wanted)
    walking.branches.update(zip(wanted, found))
    records = concurrently.each(lambda each: _examine(walking, each), read)
    examined = {each.reference: record for each, record in zip(read, records)}
    return {each.reference: {**occupied, **examined}[each.reference] for each in wave}


def _named(walking: _Walking, references: Sequence[str]) -> Sequence[world.Record]:
    # the items read whatever the walk reached, in the order named
    found = concurrently.each(lambda each: _by_reference(walking, each), references)
    return list(_each(walking, list(filter(None, found))).values())


def read_world(reading: Reading, extent: readextent.Extent) -> world.World:
    """Read what a command decides from: once, and no more than the answer needs.

    Args:
        reading: what the read starts from.
        extent: how much the command asks to be read.

    Returns:
        The world.
    """
    read = pullsearch.opened(reading.github, reading.settings)
    released = reading.released(list(read.read), reading.book)
    reading = dataclasses.replace(reading, book=released)
    walking = _Walking(
        reading=reading,
        read=read,
        stop=workorder.stop_count(reading.book),
        every_pull=extent.every_pull,
        branches={},
        held=holdissues.read(reading.github, reading.settings),
    )
    walked = walk(walking)
    return world.World(
        grounds=_grounds(walking),
        walk=walked,
        named=_named(walking, _asked_for(reading, extent)),
        act=reading.acts(),
    )


def _asked_for(reading: Reading, extent: readextent.Extent) -> Sequence[str]:
    # the items read whatever the walk reached: those the command names, the
    # pull request of the branch it pushes, the owner's priorities
    named = [
        *extent.named,
        *readextent.pushed(reading.github, extent),
        *reading.settings.slots.owner_priorities,
    ]
    return list(dict.fromkeys(named))

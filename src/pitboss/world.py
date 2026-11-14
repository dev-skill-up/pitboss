"""The world one command reads, once, before anything is decided (keyword: one-path).

``readworld.read_world`` is the only code that makes it, and ``decide.decide`` the
only code that decides from it. Every record is frozen and no field has a default,
so a record is whole or not made: a read that failed after its tries
(``retrying``) fails the command, never a field.
"""

import dataclasses
from typing import AbstractSet, Callable, Mapping, Sequence, assert_never


from . import actfacts, blockedstep, gatefacts, holdconfig, holdparse, listed
from . import pullfacts, pullrecords, shapes, sharedstep, slotbook, stuckwords

# keyword: gate: a PR's gate, with its repository's holds
GateRead = Callable[[pullfacts.PullRead, Sequence[pullrecords.Hold]], gatefacts.Gate]
PullReader = Callable[[listed.Listed], pullfacts.PullRead]  # one PR, read once a run
Others = Sequence[listed.Listed]  # the other open rows of a pull request's repository
SharedRead = Callable[[pullfacts.PullFacts, Others], Sequence[sharedstep.Shared]]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Closures:
    """How the closures of a pull request that need more than its own reads are read.

    Attributes:
        gated: what a PR at the merge or the undraft step is gated on
            (``gateread.reader``, keyword: gate).
        shared: the groups a red PR's failed checks are in, given the other open
            rows of its repository (``sharedred.closure``, keyword: shared-red).
    """

    gated: GateRead
    shared: SharedRead


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullRecord:
    """An open pull request examined, with its closure.

    Attributes:
        row: its listing row.
        facts: what was read of it (``decide.facts_of`` gives its step).
        blocked_by: what its ``Blocked-by:`` lines name, as read (``blockedby``).
        shared: the groups of failed checks it shares with other holders of its
            repository (``sharedred``), read when it is at the fix of its CI.
        waits: the open items it waits for besides its ``Blocked-by:`` lines (the
            blockers of the tickets it fixes, a refusal's, an allowlist's);
            ``blockers_of`` joins them to the open ones its lines name.
        stuck: each run of its head queued past ``stuckci.MINUTES`` while later
            runs completed, as read (keyword: stuck-ci; ``decide`` says the step).
        gated: what its merge or undraft is gated on, read only at those steps
            (keyword: gate); None at any other step.
        failures: what was read of each failed check, by its id, read only when
            the step is a fix of the CI (``mechanical`` classifies them).
    """

    row: listed.Listed
    facts: pullfacts.PullRead
    blocked_by: blockedstep.Closure
    shared: Sequence[sharedstep.Shared]
    waits: Sequence[str]
    stuck: Sequence[stuckwords.Stuck]
    gated: gatefacts.Gate | None
    failures: Mapping[int, shapes.Failure]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class TicketRecord:
    """An open ticket examined, with its closure.

    Attributes:
        reference: its ``owner/name#number``.
        issue: the ticket as listed.
        priority: the index of its priority label (the last when it has none).
        superseded: the configuration or a comment marks it superseded.
        blockers: the open items it says it waits for (``ticketblock``).
        opens_ready: its repository opens pull requests ready (keyword: no-drafts).
        branch_named: the tickets the head branches of its repository's open pull
            requests name (``pullnames.names``, keyword: taken: a branch that ends
            in its number works on it).
    """

    reference: str
    issue: shapes.Issue
    priority: int
    superseded: bool
    blockers: Sequence[str]
    opens_ready: bool
    branch_named: AbstractSet[str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Occupied:
    """An item the walk reached and did not read: its grounds already decide it.

    ``decide.pull_kept`` or ``decide.ticket_kept`` says from the grounds alone that
    no actor takes it (a slot holds
    it, a pull request works on it, a hold covers its repository).

    Attributes:
        reference: its ``owner/name#number``.
        pull: whether it is a pull request (else a ticket).
    """

    reference: str
    pull: bool


Record = PullRecord | TicketRecord | Occupied


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Stopped:
    """The walk reached its stop count of decisions.

    Attributes:
        examined: the records, in the order they were examined.
        stop: the stop count, ``max(5, the slots configured)``.
    """

    examined: Sequence[Record]
    stop: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Exhausted:
    """The walk read the last page of the last label of every repository.

    Attributes:
        examined: the records, in the order they were examined.
    """

    examined: Sequence[Record]


Walk = Stopped | Exhausted


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Grounds:
    """What is known before any item is read: ``decide`` judges occupancy from it.

    Attributes:
        listing: the open pull requests of the configuration, as listed.
        book: the slot ledger, as the live agents make it.
        holds: the owner's holds on new pull requests (``[holds]``).
        held: each repository's hold issues (``holdissues``, keyword: hold).
        quiesced: whether the owner quiesced the work (``quiesce``).
    """

    listing: Sequence[listed.Listed]
    book: slotbook.Ledger
    holds: holdconfig.Holds
    held: holdparse.Held
    quiesced: bool


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class World:
    """Everything one command decides from.

    Attributes:
        grounds: the listing, the ledger and the holds.
        walk: how the walk in the order ended, and what it examined.
        named: the records of the items examined whatever the walk reached (the
            item the command names, the owner's priorities).
        act: what the act verb the command asks for is decided from
            (``actfacts.NO_ACT`` for any other command).
        forced: the named items decided whatever keeps them (keyword: force).
    """

    grounds: Grounds
    walk: Walk
    named: Sequence[Record]
    act: actfacts.ActRead
    forced: Sequence[str] = ()


def blockers_of(record: Record) -> Sequence[str]:
    """The open items a record names as blockers.

    Args:
        record: the record.

    Returns:
        Its blockers; none for an item that was not read.
    """
    match record:
        case PullRecord():
            named = [*blockedstep.open_named(record.blocked_by), *record.waits]
            me = record.row.reference
            return [each for each in dict.fromkeys(named) if each != me]
        case TicketRecord():
            return record.blockers
        case Occupied():
            return ()
        case _:  # pragma: no cover
            assert_never(record)


def named_pulls(made: World) -> Sequence[PullRecord]:
    """The open pull requests a world read because its mode named them.

    Args:
        made: the world.

    Returns:
        Their records, in the order they were named.
    """
    return [each for each in made.named if isinstance(each, PullRecord)]


def pull_records(made: World) -> Sequence[PullRecord]:
    """The open pull requests a world read, in the order of the listing.

    Args:
        made: the world.

    Returns:
        The record of each pull request examined.
    """
    read = {
        each.row.reference: each
        for each in [*made.walk.examined, *made.named]
        if isinstance(each, PullRecord)
    }
    return [
        read[row.reference] for row in made.grounds.listing if row.reference in read
    ]

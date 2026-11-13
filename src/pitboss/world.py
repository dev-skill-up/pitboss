"""The world one command reads, once, before anything is decided (keyword: one-path).

``readworld.read_world`` is the only code that makes it, and ``decide.decide`` the
only code that decides from it. Every record is frozen and no field has a default,
so a record is whole or not made: a read that failed after its tries
(``retrying``) fails the command, never a field.
"""

import dataclasses
import enum
from typing import AbstractSet, Sequence, assert_never

from . import config, ledger, pulls, shapes


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Listed:
    """One row of an open pull requests listing (``pulls?state=open``).

    Attributes:
        reference: its ``owner/name#number``.
        repo: its repository.
        number: its number.
        title: its title.
        body: its body.
        branch: its head branch.
        draft: whether it is a draft.
        created_at: when it was opened (ISO 8601), its place in the order.
        relock: whether its head branch starts with the relock prefix; its
            review ranks after every other item.
        works_on: the tickets it works on (``pullnames.names``, keyword: taken).
    """

    reference: str
    repo: config.Repo
    number: int
    title: str
    body: str
    branch: str
    draft: bool
    created_at: str
    relock: bool
    works_on: AbstractSet[str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullRecord:
    """An open pull request examined, with its closure.

    Attributes:
        listed: its listing row.
        facts: what was read of it, its step settled by its blockers, its
            shared red and its hand-back (``blockedby``, ``sharedred``,
            ``finishpartial``).
        blockers: the open items it names as blockers, which take its place.
        stuck: the ``STUCK CI`` line of each run of its head queued past
            ``stuckci.MINUTES`` while later runs completed (keyword: stuck-ci).
    """

    listed: Listed
    facts: pulls.PullFacts
    blockers: Sequence[str]
    stuck: Sequence[str]


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
    """

    reference: str
    issue: shapes.Issue
    priority: int
    superseded: bool
    blockers: Sequence[str]
    opens_ready: bool


class Keeper(enum.Enum):
    """What the listings or the ledger say of an item, with no read of it.

    Attributes:
        SLOT: a slot of the ledger works on it.
        PULL: an open pull request works on it (keyword: taken).
        HOLD: its repository is under the owner's hold (``holds.standing``).
    """

    SLOT = enum.auto()
    PULL = enum.auto()
    HOLD = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Kept:
    """An item the walk reached and did not read: what is known of it decides it.

    Attributes:
        reference: its ``owner/name#number``.
        by: what keeps it.
    """

    reference: str
    by: Keeper


Record = PullRecord | TicketRecord | Kept


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Stopped:
    """The walk reached its stop count of decisions.

    Attributes:
        examined: the records, in the order they were examined.
    """

    examined: Sequence[Record]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Exhausted:
    """The walk read the last page of the last label of every repository.

    Attributes:
        examined: the records, in the order they were examined.
    """

    examined: Sequence[Record]


Walk = Stopped | Exhausted


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class World:
    """Everything one command decides from.

    Attributes:
        listing: every open pull request of the configuration, as listed.
        walk: how the walk in the order ended, and what it examined.
        named: the records of the items examined whatever the walk reached (the
            item the command names, the owner's priorities).
        book: the slot ledger, as the live agents make it.
        free: how many slots are free now.
        stop: the stop count, ``max(5, the slots configured)``.
    """

    listing: Sequence[Listed]
    walk: Walk
    named: Sequence[Record]
    book: ledger.Ledger
    free: int
    stop: int


def reference_of(record: Record) -> str:
    """The item a record is of.

    Args:
        record: the record.

    Returns:
        Its ``owner/name#number``.
    """
    match record:
        case PullRecord():
            return record.listed.reference
        case TicketRecord() | Kept():
            return record.reference
        case _:  # pragma: no cover
            assert_never(record)


def blockers_of(record: Record) -> Sequence[str]:
    """The open items a record names as blockers.

    Args:
        record: the record.

    Returns:
        Its blockers; none for an item that was not read.
    """
    match record:
        case PullRecord() | TicketRecord():
            return record.blockers
        case Kept():
            return ()
        case _:  # pragma: no cover
            assert_never(record)

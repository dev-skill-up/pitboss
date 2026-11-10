"""The brief of one ticket or PR, read from that item and its repository alone.

``slots next TICKET`` used to build the whole order to find one item in it. The
item's pick is made from the item itself (``itempick``) and its brief printed
with the place it stood in the last full ``slots next`` (keyword: item-brief,
place-cache, pitboss#443). A ticket with no priority label may be offered only
as the dependency of another, which only the whole order knows, so it is left
to the whole order.
"""

import enum
import sys
from typing import Callable, Sequence

from . import (
    blockers,
    config,
    itempick,
    ledger,
    nextfound,
    offering,
    placeline,
    pullmarks,
    pullread,
    pulls,
    queue,
    shapes,
    slotholding,
    suggest,
    sweepline,
    work,
    workitem,
)

Runs = Callable[[], Sequence[queue.QueueRun]]
UNKNOWN = (
    "UNKNOWN: {reference} is not in the order of slots next: {why} (a held or"
    " blocked ticket and a PR at a wait are not)"
)


class Outcome(enum.Enum):
    """What the fast path made of an item.

    Attributes:
        PRINTED: its brief was printed.
        UNKNOWN: ``slots next`` offers nothing for it.
        WHOLE: only the whole order can say.
    """

    PRINTED = enum.auto()
    UNKNOWN = enum.auto()
    WHOLE = enum.auto()


def _ticket(
    found: nextfound.Found,
    repo: config.Repo,
    reference: str,
    ticket: blockers.Ticket,
) -> suggest.Pick:
    # raises Unknown for a ticket a hold, a PR, a blocker or a supersession keeps back
    ranked = itempick.priority(found.settings, reference, ticket.labels)
    count, named = itempick.taken(found, repo, reference)
    if repo.slug in offering.standing(found, [repo.slug] * count):
        raise itempick.Unknown(f"no new pull requests in {repo.slug}: it is held")
    if named:
        raise itempick.Unknown("an open PR already works on it")
    itempick.kept_back(found, reference, ticket)
    item = workitem.of_ticket(reference, ticket, ranked)
    return suggest.Pick(
        reference=reference,
        title=ticket.title,
        category=item.category,
        item=item,
        pull=None,
    )


def _step(read: pulls.PullFacts, found: nextfound.Found) -> suggest.Pick:
    # the pick of a PR that was read: a ruling, a round, or nothing
    if pulls.reference(read) in pullmarks.pull_marks(found, [read]):
        raise itempick.Unknown("its ticket waits for an open ticket or PR")
    source = suggest.sourced(found, [read], work.pull_items([read]), {})
    chosen = suggest.picks(source)
    if not chosen:
        raise itempick.Unknown("its step is a wait")
    return chosen[0]


def _pull(
    found: nextfound.Found, repo: config.Repo, reference: str, runs: Runs
) -> suggest.Pick:
    undraft = sweepline.undraft_check(found.github, found.settings, found.now, runs)
    undraft()  # the look at the runners is made whether or not this PR asks
    number = int(reference.rpartition("#")[2])
    read = pullread.read_one(found.github, found.settings, undraft, (repo, number))
    if isinstance(read, shapes.Unreadable):
        raise itempick.Unknown(f"the PR cannot be read ({read.call}: {read.status})")
    return _step(read, found)


def _picked(
    found: nextfound.Found, live: ledger.Ledger, reference: str, runs: Runs
) -> suggest.Pick:
    # what one item is: raises Unknown when slots next offers nothing for it, and
    # Whole when only the whole order can tell
    if reference in {each.task for each in live.slots if each.agent}:
        raise itempick.Unknown("a slot already works on it")
    slug = reference.rpartition("#")[0]
    repos = {each.slug: each for each in config.repositories(found.settings)}
    if slug not in repos:
        raise itempick.Unknown(f"{slug} is not a configured repository")
    ticket = blockers.read(found.github, reference)
    if ticket is None or not ticket.open:
        raise itempick.Unknown("it is closed or cannot be read")
    if ticket.pull:
        return _pull(found, repos[slug], reference, runs)
    return _ticket(found, repos[slug], reference, ticket)


def _print(found: nextfound.Found, live: ledger.Ledger, pick: suggest.Pick) -> None:
    # the place line, then the brief
    facts = [pick.pull] if pick.pull else []
    items = [pick.item] if pick.item else []
    made = suggest.suggest(suggest.sourced(found, facts, items, live.failed), pick)
    ruled = pick.item is None  # a ruling is owed before the whole order
    place = placeline.RULING if ruled else placeline.line(found, pick.reference)
    print(f"{place}: {made.kind.value}: {made.reference}: {made.model}")
    print(made.text)


def show(
    found: nextfound.Found,
    book: ledger.Ledger,
    reference: str,
    runs: Runs,
) -> Outcome:
    """Print the brief of one PR or ticket, the way the first suggestion prints it.

    The first line says where the item stood in the last full ``slots next``
    and that it is from then (keyword: place-cache).

    Args:
        found: the context.
        book: the slot ledger.
        reference: ``owner/repo#N``.
        runs: reads the merge-queue runs of the repositories that share runners.

    Returns:
        ``PRINTED``; ``UNKNOWN`` after saying why on standard error; ``WHOLE``
        when the whole order must be read to tell.
    """
    live = slotholding.live(found.args, book)
    try:
        pick = _picked(found, live, reference, runs)
    except itempick.Whole:
        return Outcome.WHOLE
    except itempick.Unknown as refused:
        print(UNKNOWN.format(reference=reference, why=refused), file=sys.stderr)
        return Outcome.UNKNOWN
    _print(found, live, pick)
    return Outcome.PRINTED

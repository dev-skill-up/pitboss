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

from gather.commands import add_argument

from . import (
    blockers,
    brief,
    briefsave,
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
    quiesce,
    shapes,
    slotholding,
    suggest,
    sweepline,
    work,
    workitem,
)

Runs = Callable[[], Sequence[queue.QueueRun]]
FORCED = "FORCED: the plain command refuses: {text}"
FORCE_ARGUMENT = add_argument(
    "--force",
    action="store_true",
    default=False,
    help="for 'slots next TICKET': print the brief the item would get if it were"
    " startable even when the plain command answers UNKNOWN (a PR matched, a hold,"
    " a blocker); what was overridden is printed on standard error as FORCED: the"
    " plain command refuses: <its UNKNOWN text>; the ledger is not changed",
)
UNKNOWN = (
    "UNKNOWN: {reference} is not in the order of slots next: {why} (a held or"
    " blocked ticket and a PR at a wait are not)"
)
STEP_RULE = (
    "--step review prints the brief of a PR only when its step is a review"
    " (of the Plan, the Execution, a resolution, a fix round or a relock)"
)
STEP_ARGUMENT = add_argument(
    "--step",
    choices=("review",),
    default=None,
    help="for 'slots next TICKET': "
    + STEP_RULE
    + "; otherwise it exits 1 with UNKNOWN and the PR's actual step on standard error",
)
NOT_A_PULL = f"it is a ticket with no PR, which is at no review; {STEP_RULE}"
UNKNOWN_STEP = "UNKNOWN: {reference} is not at the review step: {why}"


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
    forced: bool = False,
) -> suggest.Pick:
    # raises Unknown for a ticket a hold, a PR, a blocker or a supersession keeps back,
    # unless forced (D3, keyword: force-brief), which builds the pick all the same
    try:
        ranked = itempick.priority(found.settings, reference, ticket.labels)
    except itempick.Whole:
        if not forced:
            raise
        ranked = 0
    if not forced:
        count, named = itempick.taken(found, repo, reference)
        if repo.slug in offering.standing(found, [repo.slug] * count):
            raise itempick.Unknown(f"no new pull requests in {repo.slug}: it is held")
        if named:
            raise itempick.Unknown(f"an open PR already works on it: {named}")
        itempick.kept_back(found, reference, ticket)
    item = workitem.of_ticket(reference, ticket, ranked)
    return suggest.Pick(
        reference=reference,
        title=ticket.title,
        category=item.category,
        item=item,
        pull=None,
    )


def _step(
    read: pulls.PullFacts, found: nextfound.Found, forced: bool = False
) -> suggest.Pick:
    # the pick of a PR that was read: a ruling, a round, or nothing
    if not forced and pulls.reference(read) in pullmarks.pull_marks(found, [read]):
        raise itempick.Unknown("its ticket waits for an open ticket or PR")
    source = suggest.sourced(found, [read], work.pull_items([read]), {})
    chosen = suggest.picks(source)
    if not chosen:
        raise itempick.Unknown("its step is a wait")
    return chosen[0]


def _pull(
    found: nextfound.Found,
    repo: config.Repo,
    reference: str,
    runs: Runs,
    forced: bool = False,
) -> suggest.Pick:
    undraft = sweepline.undraft_check(found.github, found.settings, found.now, runs)
    undraft()  # the look at the runners is made whether or not this PR asks
    number = int(reference.rpartition("#")[2])
    read = pullread.read_one(found.github, found.settings, undraft, (repo, number))
    if isinstance(read, shapes.Unreadable):
        raise itempick.Unknown(f"the PR cannot be read ({read.call}: {read.status})")
    return _step(read, found, forced)


def _picked(
    found: nextfound.Found,
    live: ledger.Ledger,
    reference: str,
    runs: Runs,
    forced: bool = False,
) -> suggest.Pick:
    # what one item is: raises Unknown when slots next offers nothing for it, and
    # Whole when only the whole order can tell
    held = reference in {each.task for each in live.slots if each.agent}
    if held and not forced:
        raise itempick.Unknown("a slot already works on it")
    slug = reference.rpartition("#")[0]
    repos = {each.slug: each for each in config.repositories(found.settings)}
    if slug not in repos:
        raise itempick.Unknown(f"{slug} is not a configured repository")
    ticket = blockers.read(found.github, reference)
    if ticket is None or not ticket.open:
        raise itempick.Unknown("it is closed or cannot be read")
    if ticket.pull:
        return _pull(found, repos[slug], reference, runs, forced)
    return _ticket(found, repos[slug], reference, ticket, forced)


def _print(
    found: nextfound.Found, made: suggest.Suggestion, pick: suggest.Pick
) -> None:
    # the place line, then the brief
    ruled = pick.item is None  # a ruling is owed before the whole order
    place = placeline.RULING if ruled else placeline.line(found, pick.reference)
    print(f"{place}: {made.kind.value}: {made.reference}: {made.model}")
    print(made.text)
    ledger_file = found.settings.slots.ledger
    saved = briefsave.save(ledger_file, made.reference, made.model, made.text)
    print(saved, file=sys.stderr)  # the brief on standard output is the brief alone


def _made(
    found: nextfound.Found, live: ledger.Ledger, pick: suggest.Pick
) -> suggest.Suggestion:
    facts = [pick.pull] if pick.pull else []
    items = [pick.item] if pick.item else []
    return suggest.suggest(suggest.sourced(found, facts, items, live.failed), pick)


def _overridden(
    found: nextfound.Found, live: ledger.Ledger, reference: str, runs: Runs
) -> suggest.Pick | None:
    # the pick the plain command refused (D3, keyword: force-brief); none when the
    # item has no step to brief (a PR at a wait) or cannot be read
    try:
        return _picked(found, live, reference, runs, True)
    except (itempick.Whole, itempick.Unknown):
        return None


def _attempt(
    found: nextfound.Found, book: ledger.Ledger, reference: str, runs: Runs
) -> tuple[ledger.Ledger, suggest.Pick | Outcome]:
    # the ledger as live, and the pick or why there is none: UNKNOWN (said on
    # standard error) or WHOLE
    live = slotholding.live(found.args, book)
    if quiesce.is_on(found.settings.slots.ledger):  # D11
        print(quiesce.REFUSED.format(reference=reference), file=sys.stderr)
        return live, Outcome.UNKNOWN
    try:
        return live, _picked(found, live, reference, runs)
    except itempick.Whole:
        return live, Outcome.WHOLE
    except itempick.Unknown as refused:
        text = UNKNOWN.format(reference=reference, why=refused)
        if getattr(found.args, "force", False):
            overridden = _overridden(found, live, reference, runs)
            if overridden is not None:
                print(FORCED.format(text=text), file=sys.stderr)
                return live, overridden
        print(text, file=sys.stderr)
        return live, Outcome.UNKNOWN


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
    live, pick = _attempt(found, book, reference, runs)
    if isinstance(pick, Outcome):
        return pick
    _print(found, _made(found, live, pick), pick)
    return Outcome.PRINTED


def _refused(reference: str, why: str) -> Outcome:
    print(UNKNOWN_STEP.format(reference=reference, why=why), file=sys.stderr)
    return Outcome.UNKNOWN


def show_review(
    found: nextfound.Found,
    book: ledger.Ledger,
    reference: str,
    runs: Runs,
) -> Outcome:
    """Print the brief of a PR only if its step is a review (``--step review``).

    Args:
        found: the context.
        book: the slot ledger.
        reference: ``owner/repo#N``.
        runs: reads the merge-queue runs of the repositories that share runners.

    Returns:
        ``PRINTED``; ``UNKNOWN`` after saying on standard error that the PR is
        not at the review step, with its actual step and the rule (keyword:
        step-review, pitboss#462). Never ``WHOLE``: a ticket with no PR is at
        no review.
    """
    live, pick = _attempt(found, book, reference, runs)
    if pick is Outcome.WHOLE:
        return _refused(reference, NOT_A_PULL)
    if isinstance(pick, Outcome):
        return pick
    made = _made(found, live, pick)
    if made.kind not in brief.REVIEWS:
        return _refused(reference, f"its step is `{made.kind.value}`; {STEP_RULE}")
    _print(found, made, pick)
    return Outcome.PRINTED

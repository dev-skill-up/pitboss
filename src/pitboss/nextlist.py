"""What to start next: the list, the empty slots and the briefs (keyword: brief).

Shared by ``slots next`` and ``next`` with no ticket (pitboss#118); it does not
import ``commands``, so the commands can import it.
"""

import dataclasses
import functools
import itertools
import sys
from typing import Callable, Iterable, Sequence, TypeVar

from . import (
    assigning,
    config,
    configfile,
    diskwatch,
    fixwait,
    handedback,
    ledger,
    listtail,
    logline,
    nextfound,
    nextmade,
    nextsource,
    nextview,
    nothead,
    offering,
    pullmarks,
    pullstate,
    pulls,
    quiesce,
    rankline,
    readyline,
    skipitem,
    slotheld,
    slotholding,
    slotlog,
    slotsheader,
    suggest,
    timing,
    unlabeledsearch,
    unqueued,
    unreadableline,
    windowrun,
    windowstage,
    work,
)
from .markers import Marker

Found = nextfound.Found
require_ledger = nextfound.require_ledger
Reads = nextview.Reads
Opened = Sequence[pulls.Read]


def _live(found: Found, opened: Opened, book: ledger.Ledger) -> ledger.Ledger:
    done = handedback.agents(found, opened, book)
    return slotholding.live(found.args, book, done)


def _counted(found: Found, opened: Opened, book: ledger.Ledger) -> work.Offered:
    offer = offering.offered(found, _scope(found, opened), book)
    return slotholding.counted(offer, opened, book, found.args)


def _scope(found: Found, opened: Sequence[pulls.Read]) -> offering.Look:
    # the open PRs and the ones whose tickets wait
    return offering.Look(opened=opened, marks=pullmarks.pull_marks(found, opened))


def _windowed(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> work.Offered:
    # the offer over as small a window of tickets as shows the top (windowrun)
    scope = _scope(found, opened)
    count = windowrun.WINDOW
    while True:
        staged = functools.partial(windowstage.start, found, opened, book, count)
        offer = offering.offered(found, dataclasses.replace(scope, staged=staged), book)
        if not offer.unread or len(offer.items) >= suggest.TOP:
            return slotholding.counted(offer, opened, book, found.args)
        count *= windowrun.GROWTH


def _ordered(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> work.Offered:
    unreadableline.print_withheld(opened)
    return _counted(found, opened, book)


def show(
    found: Found,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
) -> None:
    """Print what to start next: the list, the empty slots and the briefs.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger.
    """
    logline.post(found.settings.slots.log)
    if quiesce.say(found.settings.slots.ledger):  # D11: nothing is offered
        return
    book = _live(found, opened, book)
    unreadableline.print_withheld(opened)
    skipped = skipitem.apply(found.args, found.settings.project.repo)
    ordered, skip_lines = skipped(_windowed(found, opened, book))
    timing.note(found.args, "ranking", len(ordered.items), "items")
    for line in _listed(found, (opened, ordered), book, skip_lines):
        print(line)
    timing.note(found.args, "lists and briefs printed", suggest.TOP, "briefs at most")


def _assigned(
    ordered: work.Offered, book: ledger.Ledger, slots: config.Slots
) -> Sequence[work.Assignment]:
    # a PR whose round holds a slot is not given another one (keyword: slot-held)
    taken = ordered.occupancy
    if not taken.known:
        return []
    rest = [each for each in ordered.items if each.reference not in taken.references]
    return assigning.assign(rest, book, slots)[: taken.free]


def _view(
    found: Found,
    ordered: work.Offered,
    book: ledger.Ledger,
    reads: Reads | None = None,
) -> nextview.NextView:
    reads = reads or Reads()
    return nextview.NextView(
        items=ordered.items,
        assignments=_assigned(ordered, book, found.settings.slots),
        occupancy=ordered.occupancy,
        slots=found.settings.slots,
        failed=book.failed,
        now=found.now,
        withheld=nextview.hold_notes(found.settings, ordered, book, reads.opened),
        ranked=list(rankline.lines(ordered)),
        ready=list(readyline.texts(found.settings, reads.facts, found.now)),
        no_drafts=found.settings.project.no_drafts,
    )


def _source(
    found: Found, opened: Opened, ordered: work.Offered, book: ledger.Ledger
) -> suggest.Source:
    volume = diskwatch.read(found.args.usage, found.settings.project.workspace)
    got = suggest.sourced(
        found, pullmarks.awake(opened, ordered), ordered.items, book.failed
    )
    big = nextsource.big(found, volume)
    return dataclasses.replace(got, volume=volume, big=big, occupancy=ordered.occupancy)


def _listed(
    found: Found,
    read: tuple[Sequence[pulls.Read], work.Offered],
    book: ledger.Ledger,
    skip_lines: Sequence[str],
) -> Iterable[str]:
    # the lines of the list, from the source of its suggestions
    opened, ordered = read
    source = _source(found, opened, ordered, book)
    view = _view(found, ordered, book, Reads(facts=source.facts, opened=opened))
    nextmade.recorded(found, ordered, (view.items, len(view.ready)))
    return itertools.chain(
        header(found, book, view),
        fixwait.lines(source.facts, found.now, nextsource.held(ordered, book)),
        unlabeledsearch.lines(found.github, found.settings),
        skip_lines,
        nextview.next_lines(view),
        _after(found, ordered, source, view),
    )


def _after(
    found: Found, ordered: work.Offered, source: suggest.Source, view: nextview.NextView
) -> Iterable[str]:
    return itertools.chain(
        [windowrun.UNREAD.format(count=len(view.items))] if ordered.unread else [],
        offering.disagreements(found, ordered),
        pullstate.lines(found.github, found.settings, source.facts),
        listtail.lines(found, source.facts, source.volume),
        suggest.lines(source),
    )


def header(found: Found, book: ledger.Ledger, view: nextview.NextView) -> Sequence[str]:
    """The lines before the list (``LEDGER STALE``, ``SLOTS``, ``FREE SLOT``).

    Args:
        found: the context.
        book: the ledger as the live agents make it.
        view: what the list prints from.

    Returns:
        The lines (keyword: slots-header, pitboss#415).
    """
    slots = found.settings.slots
    stale = (
        []
        if getattr(found.args, "running", None) is not None
        else slotsheader.stale_line(ledger.configured(found.settings), slots.ledger)
    )
    cap = len(slots.default) or len(book.slots)
    since = slotsheader.free_since(book, slots.log, found.now)
    return [*stale, *slotsheader.lines(book, cap, since, nextview.start_text(view))]


def startable_view(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> nextview.NextView:
    """The view a free slot starts from, read afresh.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger.

    Returns:
        The view; ``nextview.startable`` gives the items in order.
    """
    book = _live(found, opened, book)
    ordered = _counted(found, opened, book)
    awake = pullmarks.awake(opened, ordered)
    return _view(found, ordered, book, Reads(facts=awake, opened=opened))


def show_all(found: Found, opened: Sequence[pulls.Read]) -> None:
    """Print the list of ``next`` with no ticket: the ledger must exist.

    Args:
        found: the context.
        opened: the open PRs, read or not.
    """
    require_ledger(found.settings.slots.ledger)
    show(found, opened, ledger.configured(found.settings))


def head_line(found: Found, opened: Sequence[pulls.Read], ticket: str) -> Sequence[str]:
    """The ``NOT THE HEAD`` line of a ticket, read from the queue just now.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        ticket: the ticket whose brief is printed.

    Returns:
        The line, or none when the ticket is the head.
    """
    given = configfile.named(found.args)
    view = startable_view(found, opened, ledger.configured(found.settings))
    items = nextview.startable(view)
    return nothead.line(items, found.settings.slots.priority_labels, ticket, given)


Context = TypeVar("Context", bound=Found)


def free_line_by(
    opened: Callable[[Context], Sequence[pulls.Read]],
) -> Callable[[Context, ledger.Ledger, int], str]:
    """The ``SLOT FREE`` line maker of a reader of the open PRs.

    Args:
        opened: reads the open PRs of a context.

    Returns:
        A function of a context, the ledger and the cap that makes the line.
    """

    def make(found: Context, book: ledger.Ledger, cap: int) -> str:
        return free_line(found, opened(found), book, cap)

    return make


def free_line(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger, cap: int
) -> str:
    """The ``SLOT FREE`` line, naming the first startable item.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the ledger.
        cap: the number of slots.

    Returns:
        The line.
    """
    since = slotsheader.free_since(book, found.settings.slots.log, found.now)
    free = cap - len(slotsheader.running(book))
    return (
        f"{Marker.WATCH_SLOT_FREE.text}: {free} of {cap} free since"
        f" {slotlog.utc(since).strftime(slotsheader.TIME_FORMAT)}; first startable:"
        f" {first_startable(found, opened, book)}"
    )


def first_startable(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> str:
    """The first startable item with its command, as ``SLOT FREE`` names it.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the ledger.

    Returns:
        The item, or that nothing is queued.
    """
    view = startable_view(found, opened, book)
    return nothead.first(
        nextview.startable(view), view.items, configfile.named(found.args)
    )


UNKNOWN = (
    "UNKNOWN: {reference} is not in the order of slots next: no open PR is at a"
    " step that is offered and no open ticket is queued (a held or blocked"
    " ticket and a PR at a wait are not); {why}"
)


def _placed(view: nextview.NextView, pick: suggest.Pick) -> str:
    return nextview.place_line(view, pick.reference)


def _picked(source: suggest.Source, reference: str) -> suggest.Pick | None:
    every = suggest.picks(dataclasses.replace(source, occupancy=slotheld.UNLIMITED))
    return next((each for each in every if each.reference == reference), None)


def show_item(
    found: Found,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
    reference: str,
) -> bool:
    """Print the brief of one PR or ticket, as if it were the first suggestion.

    The first line says where the item stands in the order of ``slots next``
    (``NEXT 24 of 30, out of order, 22 ahead of it``), then the kind, the item
    and the model class; the brief that follows is the suggestion's own text.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger.
        reference: ``owner/repo#N``.

    Returns:
        False, with ``UNKNOWN`` on standard error, when ``slots next`` offers
        nothing for the item.
    """
    book = _live(found, opened, book)
    ordered = _counted(found, opened, book)
    source = _source(found, opened, ordered, book)
    pick = _picked(source, reference)
    if pick is None:
        why = unqueued.why(found.github, ordered, reference)
        print(UNKNOWN.format(reference=reference, why=why), file=sys.stderr)
        return False
    made = suggest.suggest(source, pick)
    place = _placed(_view(found, ordered, book, Reads(facts=source.facts)), pick)
    print(f"{place}: {made.kind.value}: {made.reference}: {made.model}")
    print(made.text)
    return True


def refill(
    found: Found,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
    name: str,
) -> None:
    """Print the ``slots next`` line of one empty slot (``slots free`` prints it).

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger, in which the slot is empty.
        name: the slot.
    """
    book = _live(found, opened, book)
    ordered = _ordered(found, opened, book)
    if not ordered.occupancy.known:
        print(slotheld.NOT_COMPUTED)
        return
    print(nextview.refill_line(_view(found, ordered, book), name))

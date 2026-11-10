"""What to start next: the list, the empty slots and the briefs (keyword: brief).

Shared by ``slots next`` and ``next`` with no ticket (pitboss#118); it does not
import ``commands``, so the commands can import it.
"""

import dataclasses
import itertools
import pathlib
import sys
from typing import Callable, Sequence, TypeVar

from . import (
    assigning,
    config,
    configfile,
    diskwatch,
    exempt,
    ledger,
    logline,
    machine,
    nextfound,
    nextview,
    nothead,
    offering,
    pullmarks,
    pulls,
    pullstate,
    rankline,
    readyline,
    slotheld,
    slotholding,
    slotlog,
    slotsheader,
    suggest,
    unlabeled,
    unreadableline,
    work,
)
from .markers import Marker

Found = nextfound.Found
require_ledger = nextfound.require_ledger
Reads = nextview.Reads


def _live(found: Found, book: ledger.Ledger) -> ledger.Ledger:
    # pitboss#94: the agents that run, not the hand's rows
    return slotholding.derived(book, getattr(found.args, "running", None))


def _counted(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> work.Offered:
    offer = offering.offered(found, opened, book, pullmarks.pull_marks(found, opened))
    return slotholding.counted(offer, opened, book, found.args)


def _ordered(
    found: Found, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> work.Offered:
    unreadableline.print_withheld(opened)
    return _counted(found, opened, book)


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


def _big(found: Found, volume: diskwatch.Reading | None) -> Sequence[diskwatch.Big]:
    # keyword: disk-watch (pitboss#288): walked only when the suggestion is due
    if volume is None or not volume.crowded:
        return []
    return diskwatch.largest(machine.real(), found.clean.scratch)


def _source(
    found: Found,
    opened: Sequence[pulls.Read],
    ordered: work.Offered,
    book: ledger.Ledger,
) -> suggest.Source:
    volume = diskwatch.read(found.args.usage, found.settings.project.workspace)
    given = configfile.named(found.args)
    return suggest.Source(
        github=found.github,
        settings=found.settings,
        given=given,
        brief=configfile.load_brief(
            given, pathlib.Path(found.args.env.get("PWD", "."))
        ),
        facts=pullmarks.awake(opened, ordered),
        items=ordered.items,
        failed=book.failed,
        volume=volume,
        big=_big(found, volume),
        occupancy=ordered.occupancy,
    )


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
    book = _live(found, book)
    ordered = _ordered(found, opened, book)
    source = _source(found, opened, ordered, book)
    view = _view(found, ordered, book, Reads(facts=source.facts, opened=opened))
    for line in itertools.chain(
        header(found, book, view),
        unlabeled.lines(found.github, found.settings),
        nextview.next_lines(view),
        offering.disagreements(found, ordered),
        pullstate.lines(found.github, found.settings, source.facts),
        [diskwatch.line(source.volume)] if source.volume else [],
        [exempt.OVERRIDE],  # keyword: pitboss-exempt (pitboss#113)
        suggest.lines(source),
    ):
        print(line)


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
    book = _live(found, book)
    ordered = _counted(found, opened, book)
    awake = pullmarks.awake(opened, ordered)
    return _view(found, ordered, book, Reads(facts=awake, opened=opened))


def brief_command(given: str, item: str) -> str:
    """The command that prints the brief of an item.

    Args:
        given: the configuration as the command was given it.
        item: the ticket or PR.

    Returns:
        The command.
    """
    return f"pitboss slots next {item} --config {given}"


def _first(view: nextview.NextView, given: str) -> str:
    items = nextview.startable(view)
    if items:
        return f"{items[0].reference} ({brief_command(given, items[0].reference)})"
    if view.items:
        held = view.items[0].reference
        return (
            f"{held} ({brief_command(given, held)}), offered because a ticket of"
            " its repository is in flight"
        )
    return "no open ticket or PR is queued: file the next ticket"


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
    view = startable_view(found, opened, book)
    since = slotsheader.free_since(book, found.settings.slots.log, found.now)
    free = cap - len(slotsheader.running(book))
    return (
        f"{Marker.WATCH_SLOT_FREE.text}: {free} of {cap} free since"
        f" {slotlog.utc(since).strftime(slotsheader.TIME_FORMAT)}; first startable:"
        f" {_first(view, configfile.named(found.args))}"
    )


UNKNOWN = (
    "UNKNOWN: {reference} is not in the order of slots next: no open PR is at a"
    " step that is offered and no open ticket is queued (a held or blocked"
    " ticket and a PR at a wait are not)"
)


def _place(view: nextview.NextView, pick: suggest.Pick) -> str:
    # where the item stands in the order, so a dispatch out of order is visible
    marker = Marker.NEXT.text
    if pick.item is None:
        return f"{marker} ruling, owed before every {marker} line"
    number, last = nextview.place(view, pick.reference)
    ahead = number - (slotheld.LEAD + 1)
    order = f"out of order, {ahead} ahead of it" if ahead else "first in the order"
    return f"{marker} {number} of {last}, {order}"


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
    book = _live(found, book)
    ordered = _counted(found, opened, book)
    source = _source(found, opened, ordered, book)
    every = suggest.picks(dataclasses.replace(source, occupancy=slotheld.UNLIMITED))
    pick = next((each for each in every if each.reference == reference), None)
    if pick is None:
        print(UNKNOWN.format(reference=reference), file=sys.stderr)
        return False
    made = suggest.suggest(source, pick)
    place = _place(_view(found, ordered, book, Reads(facts=source.facts)), pick)
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
    book = _live(found, book)
    ordered = _ordered(found, opened, book)
    if not ordered.occupancy.known:
        print(slotheld.NOT_COMPUTED)
        return
    print(nextview.refill_line(_view(found, ordered, book), name))

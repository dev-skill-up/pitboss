"""What to start next: the list, the empty slots and the briefs (keyword: brief).

Shared by ``slots next`` and ``next`` with no ticket (pitboss#118); it does not
import ``commands``, so the commands can import it.
"""

import argparse
import dataclasses
import datetime
import itertools
import pathlib
import sys
from typing import Protocol, Sequence

from . import (
    assigning,
    cleanconfig,
    config,
    configfile,
    diskwatch,
    exempt,
    ghapi,
    ledger,
    logline,
    machine,
    nextview,
    offering,
    pulls,
    pullmarks,
    pullstate,
    rankline,
    readyline,
    slotheld,
    slotholding,
    suggest,
    unlabeled,
    unreadableline,
    work,
)
from .markers import Marker


class Found(Protocol):
    """The part of a command's context that the list reads."""

    @property
    def github(self) -> ghapi.GitHub:
        """The API.

        Returns:
            The API.
        """

    @property
    def settings(self) -> config.Config:
        """The configuration.

        Returns:
            The configuration.
        """

    @property
    def clean(self) -> cleanconfig.Clean:
        """What ``clean-container`` looks at and keeps.

        Returns:
            The ``[clean]`` table.
        """

    @property
    def args(self) -> argparse.Namespace:
        """The parsed arguments.

        Returns:
            The arguments.
        """

    @property
    def now(self) -> datetime.datetime:
        """The time of the run.

        Returns:
            The time.
        """


def require_ledger(path: pathlib.Path) -> None:
    """Exit 1 when the ledger file is absent: it is authoritative on the slots.

    Args:
        path: the ledger file.

    Raises:
        SystemExit: 1 when the file does not exist.
    """
    if not path.exists():
        print(
            f"LEDGER MISSING: {path} does not exist. It is authoritative on"
            " the slots and the owner creates it",
            file=sys.stderr,
        )
        raise SystemExit(1)


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
    facts: Sequence[pulls.PullFacts] = (),
) -> nextview.NextView:
    return nextview.NextView(
        items=ordered.items,
        assignments=_assigned(ordered, book, found.settings.slots),
        occupancy=ordered.occupancy,
        slots=found.settings.slots,
        failed=book.failed,
        now=found.now,
        withheld=nextview.Withheld(held=ordered.held, standing=ordered.standing),
        ranked=list(rankline.lines(ordered)),
        ready=list(readyline.texts(found.settings, facts, found.now)),
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
    for line in itertools.chain(
        unlabeled.lines(found.github, found.settings),
        nextview.next_lines(_view(found, ordered, book, source.facts)),
        offering.disagreements(found, ordered),
        pullstate.lines(found.github, found.settings, source.facts),
        [diskwatch.line(source.volume)] if source.volume else [],
        [exempt.OVERRIDE],  # keyword: pitboss-exempt (pitboss#113)
        suggest.lines(source),
    ):
        print(line)


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
    place = _place(_view(found, ordered, book, source.facts), pick)
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

"""The sorted list of ``slots next``, printed (keyword: next-list)."""

import dataclasses
import datetime
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import (
    config,
    exempt,
    holds,
    ledger,
    pulls,
    slotheld,
    slotsheader,
    updateline,
    work,
)
from .markers import Marker

CATEGORY_WORDS = work.CATEGORY_WORDS


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Withheld:
    """The tickets the owner's hold keeps back.

    Attributes:
        held: the tickets.
        standing: each held repository and its open count.
        serial: the items the first startable item skips (a ticket of a serial
            repository while a ledger row works on one; keyword: slots-watch,
            pitboss#415).
        needs: what a red PR or a PR behind the base needs, by reference
            (keyword: pull-needs, pitboss#415).
    """

    held: Sequence[work.Item] = ()
    standing: Mapping[str, int] = dataclasses.field(default_factory=dict)
    serial: AbstractSet[str] = frozenset()
    needs: Mapping[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NextView:
    """What ``slots next`` prints from.

    Attributes:
        items: the ordered items.
        assignments: each empty slot and its item.
        slots: the slot configuration.
        failed: each reference's failed models.
        now: the time now.
        withheld: the tickets the owner's hold keeps back and each held
            repository's open count.
        ranked: the ``BLOCKED``, ``SUPERSEDED``, ``BLOCKS`` and ``PROMOTE``
            lines (``rankline``; keyword: ticket-blocked, blocked-pull,
            superseded-ticket, blocks-line, promote).
        ready: the texts of the NEXT lines of the drafts to mark ready, printed
            first after the running agents' line (keyword: mark-ready,
            pitboss#273).
        occupancy: what holds the slots beyond the ledger's agents (keyword:
            slot-held, pitboss#291).
        no_drafts: the repositories whose PRs open ready; the line of a ticket
            there says so (keyword: pitboss-exempt, pitboss#113).
    """

    items: Sequence[work.Item]
    assignments: Sequence[work.Assignment]
    slots: config.Slots
    failed: Mapping[str, Sequence[str]]
    now: datetime.datetime
    withheld: Withheld = Withheld()
    ranked: Sequence[str] = ()
    ready: Sequence[str] = ()
    occupancy: slotheld.Occupancy = slotheld.UNLIMITED
    no_drafts: AbstractSet[str] = frozenset()


def _age_days(created_at: str, now: datetime.datetime) -> int:
    return (now - datetime.datetime.fromisoformat(created_at)).days


def _new_pr(item: work.Item, view: NextView) -> str:
    # the priority of a ticket, and that its PR opens ready where there are no drafts
    if item.category is not work.Category.NEW_PR:
        return ""
    slug = item.reference.rpartition("#")[0]
    ready = f", {exempt.OPEN_READY}" if slug in view.no_drafts else ""
    return f" {view.slots.priority_labels[item.priority]}{ready}"


def _needs(item: work.Item, view: NextView) -> str:
    # a red PR or one behind the base is not "review it": say what it needs
    need = view.withheld.needs.get(item.reference)
    return f"; needs: {need}" if need else ""


def _item_text(item: work.Item, view: NextView) -> str:
    model = work.smallest_model(item, view.slots, view.failed) or "none left"
    return (
        f"{item.reference} ({CATEGORY_WORDS[item.category]}{_new_pr(item, view)},"
        f" opened {item.created_at[:10]}, {_age_days(item.created_at, view.now)}"
        f" days, smallest model {model}): {item.title[:60]}{_needs(item, view)}"
    )


def _queued(item: work.Item, view: NextView) -> str:
    # a step of a PR that holds a slot is that slot's own work
    waits = slotheld.waits(view.occupancy, item.reference)
    return f" {slotheld.QUEUED}" if waits else ""


def place(view: NextView, reference: str) -> tuple[int, int]:
    """Where an item of the view stands in the list, as ``next_lines`` numbers it.

    Args:
        view: what to print from.
        reference: the PR or ticket, one of the view's items.

    Returns:
        The number of its ``NEXT`` line and the number of the last ``NEXT`` line.
    """
    first = slotheld.LEAD + 1 + len(view.ready)
    found = [each.reference for each in view.items].index(reference)
    return first + found, first + len(view.items) - 1


def startable(view: NextView) -> Sequence[work.Item]:
    """The items a free slot may start, in the order of the list.

    Args:
        view: what to print from.

    Returns:
        The view's items but those a serial repository holds back.
    """
    return [each for each in view.items if each.reference not in view.withheld.serial]


def start_text(view: NextView) -> str | None:
    """The first dispatchable ``NEXT`` line of the list, as printed.

    Args:
        view: what to print from.

    Returns:
        ``NEXT <n>. <text>`` of the first draft to mark ready, else of the first
        startable item; None when the list has neither.
    """
    first = slotheld.LEAD + 1
    if view.ready:
        return f"{Marker.NEXT.text} {first}. {view.ready[0]}"
    found = startable(view)
    if not found:
        return None
    number, _ = place(view, found[0].reference)
    return f"{Marker.NEXT.text} {number}. {_item_text(found[0], view)}"


def next_lines(view: NextView) -> Iterable[str]:
    """The running agents, the sorted list, the held tickets, then the slots.

    Every step after the first waits for a free slot when no slot is free: a
    running agent is never interrupted (keyword: slot-held, pitboss#291).

    Args:
        view: what to print from.

    Yields:
        The lines.
    """
    yield f"{Marker.NEXT.text} {slotheld.LEAD}. {slotheld.RUNNING_FIRST}"
    first = slotheld.LEAD + 1
    listed = [
        *view.ready,
        *(_item_text(each, view) + _queued(each, view) for each in view.items),
    ]
    for index, text in enumerate(listed, start=first):
        yield f"{Marker.NEXT.text} {index}. {text}"
    for item in view.withheld.held:
        yield holds.held_line(item.reference, view.withheld.standing)
    yield from view.ranked
    yield from slotheld.lines(view.occupancy)
    if not view.assignments and not slotheld.lines(view.occupancy):
        yield "slots: the ledger says all full: start nothing"
    for slot, chosen in view.assignments:
        yield empty_slot_line(slot, chosen, view)


def empty_slot_line(slot: ledger.Slot, chosen: work.Item | None, view: NextView) -> str:
    """The line that says what one empty slot starts.

    Args:
        slot: the empty slot.
        chosen: the item it takes, or None when nothing fits it.
        view: what to print from.

    Returns:
        The ``EMPTY SLOT`` line.
    """
    target = "nothing fits it: leave it empty"
    if chosen is not None:
        target = "start " + _item_text(chosen, view)
    return f"{Marker.EMPTY_SLOT.text}: {slot.name} ({slot.model}): {target}"


def refill_line(view: NextView, name: str) -> str:
    """The ``slots next`` line of one empty slot, or that no task is waiting.

    Args:
        view: what to print from.
        name: the slot, which the ledger says is empty.

    Returns:
        The slot's ``EMPTY SLOT`` line when an item fits it, else
        ``no task is waiting``; the first line of what holds the slots when
        none is free.
    """
    found = next((pair for pair in view.assignments if pair[0].name == name), None)
    if found is None:
        return slotheld.lines(view.occupancy)[0]  # no free slot: something holds it
    slot, chosen = found
    if chosen is None:
        return "no task is waiting"
    return empty_slot_line(slot, chosen, view)


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reads:
    """The open PRs a view is made from.

    Attributes:
        facts: the PRs to mark ready.
        opened: every open PR, read or not.
    """

    facts: Sequence[pulls.PullFacts] = ()
    opened: Sequence[pulls.Read] = ()


def _slug(reference: str) -> str:
    return reference.rpartition("#")[0]


def serial(
    items: Sequence[work.Item],
    book: ledger.Ledger,
    slots: config.Slots,
    opened: Sequence[pulls.Read],
) -> AbstractSet[str]:
    """The tickets of a serial repository while a ledger row works on it.

    A serial repository (``[slots] serial``) takes one ticket at a time, so while
    a ledger row works on it or a PR of it is open, its new tickets are skipped.

    Args:
        items: the ordered items.
        book: the ledger.
        slots: the slot configuration.
        opened: the open PRs, read or not.

    Returns:
        The references of the tickets to skip.
    """
    busy = {_slug(slot.ticket or slot.task) for slot in slotsheader.running(book)}
    busy |= {each.repo.slug for each in pulls.readable(opened)}
    waiting = busy & set(slots.watch.serial)
    held = set()
    for each in items:
        if each.category == work.Category.NEW_PR and _slug(each.reference) in waiting:
            held.add(each.reference)
    return frozenset(held)


def hold_notes(
    settings: config.Config,
    ordered: work.Offered,
    book: ledger.Ledger,
    opened: Sequence[pulls.Read],
) -> Withheld:
    """What the list holds back, and what it says a red or behind PR needs.

    Args:
        settings: the configuration.
        ordered: the work that is queued.
        book: the ledger.
        opened: the open PRs, read or not.

    Returns:
        The held tickets, the skipped ones and the needs.
    """
    found = {
        pulls.reference(each): updateline.needs(each, settings)
        for each in pulls.readable(opened)
    }
    return Withheld(
        held=ordered.held,
        standing=ordered.standing,
        serial=serial(ordered.items, book, settings.slots, opened),
        needs={each: need for each, need in found.items() if need},
    )

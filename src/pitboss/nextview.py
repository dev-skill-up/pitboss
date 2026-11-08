"""The sorted list of ``slots next``, printed (keyword: next-list)."""

import dataclasses
import datetime
from typing import Iterable, Mapping, Sequence

from . import blockedline, config, holds, ledger, slotheld, work
from .markers import Marker

CATEGORY_WORDS = work.CATEGORY_WORDS


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NextView:
    """What ``slots next`` prints from.

    Attributes:
        items: the ordered items.
        assignments: each empty slot and its item.
        slots: the slot configuration.
        failed: each reference's failed models.
        now: the time now.
        held: the tickets the owner's hold keeps back (keyword: pr-hold).
        standing: each held repository and its open count.
        blocked: the tickets that cannot be worked on until an open ticket or
            PR (keyword: ticket-blocked).
        ready: the texts of the NEXT lines of the drafts to mark ready, printed
            first after the running agents' line (keyword: mark-ready,
            pitboss#273).
        occupancy: what holds the slots beyond the ledger's agents (keyword:
            slot-held, pitboss#291).
    """

    items: Sequence[work.Item]
    assignments: Sequence[work.Assignment]
    slots: config.Slots
    failed: Mapping[str, Sequence[str]]
    now: datetime.datetime
    held: Sequence[work.Item] = ()
    standing: Mapping[str, int] = dataclasses.field(default_factory=dict)
    blocked: Sequence[work.Item] = ()
    ready: Sequence[str] = ()
    occupancy: slotheld.Occupancy = slotheld.UNLIMITED


def _age_days(created_at: str, now: datetime.datetime) -> int:
    return (now - datetime.datetime.fromisoformat(created_at)).days


def _item_text(item: work.Item, view: NextView) -> str:
    model = work.smallest_model(item, view.slots, view.failed) or "none left"
    priority = (
        f" {view.slots.priority_labels[item.priority]}"
        if item.category is work.Category.NEW_PR
        else ""
    )
    return (
        f"{item.reference} ({CATEGORY_WORDS[item.category]}{priority},"
        f" opened {item.created_at[:10]}, {_age_days(item.created_at, view.now)}"
        f" days, smallest model {model}): {item.title[:60]}"
    )


def _queued(item: work.Item, view: NextView) -> str:
    # a step of a PR that holds a slot is that slot's own work
    waits = slotheld.waits(view.occupancy, item.reference)
    return f" {slotheld.QUEUED}" if waits else ""


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
    for item in view.held:
        yield holds.held_line(item.reference, view.standing)
    for item in view.blocked:
        yield blockedline.line(item.reference, item.blocker)
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

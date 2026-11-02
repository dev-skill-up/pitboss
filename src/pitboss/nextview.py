"""The sorted list of ``slots next``, printed (keyword: next-list)."""

import dataclasses
import datetime
from typing import Iterable, Mapping, Sequence

from . import config, work
from .markers import Marker

CATEGORY_WORDS = {
    work.Category.FIX_REVIEW: "fix the review",
    work.Category.REVISE_PLAN: "revise the plan",
    work.Category.REVIEW: "review it (a reviewer that is not its author)",
    work.Category.NEW_PR: "start a PR",
    work.Category.FIX_CI: "fix the CI (a red CI is no rejection)",
    work.Category.FIRST_ROUND: "write the Plan and Execution body",
    work.Category.RESOLVE_CONFLICT: "resolve the conflict",
    work.Category.RULING_STEPS: "do the ruling's steps",
    work.Category.RULING_AS_GIVEN: "carry out the ruling",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NextView:
    """What ``slots next`` prints from.

    Attributes:
        items: the ordered items.
        assignments: each empty slot and its item.
        slots: the slot configuration.
        failed: each reference's failed models.
        now: the time now.
    """

    items: Sequence[work.Item]
    assignments: Sequence[work.Assignment]
    slots: config.Slots
    failed: Mapping[str, Sequence[str]]
    now: datetime.datetime


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


def next_lines(view: NextView) -> Iterable[str]:
    """The sorted list, then what each empty slot takes.

    Args:
        view: what to print from.

    Yields:
        The lines.
    """
    for index, item in enumerate(view.items, start=1):
        yield f"{Marker.NEXT.text} {index}. {_item_text(item, view)}"
    if not view.assignments:
        yield "slots: the ledger says all full: start nothing"
    for slot, chosen in view.assignments:
        target = "nothing fits it: leave it empty"
        if chosen is not None:
            target = "start " + _item_text(chosen, view)
        yield f"{Marker.EMPTY_SLOT.text}: {slot.name} ({slot.model}): {target}"

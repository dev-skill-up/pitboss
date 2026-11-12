"""The order in which ``flow.next_step`` decides: a row and the reasons for the order.

(Keyword: flow-order.) ``flow.ROWS`` is the table, first row that holds first, and
``STATED`` gives the reason for the order of each two rows that can hold at once.
The module imports nothing of pitboss, so ``flow`` reads it without a level more.
"""

import dataclasses
from typing import Callable, Generic, Mapping, TypeVar

State = TypeVar("State")
Step = TypeVar("Step")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Row(Generic[State, Step]):
    """A row of the order in which ``next_step`` decides.

    Attributes:
        name: the row's name, as ``STATED`` names it.
        holds: whether the row decides this PR's step.
        step: the step it decides.
    """

    name: str
    holds: Callable[[State], bool]
    step: Callable[[State], Step]


STATED: Mapping[tuple[str, str], str] = {
    ("paused-owner", "ruling-hold"): "a PR paused for the owner is owed nothing else",
    ("paused-owner", "conflict"): "the owner decides before any fix of a conflict",
    ("paused-owner", "first-round"): "the owner decides before any first round",
    ("paused-owner", "gates"): "the owner decides before any gate",
    ("ruling-hold", "conflict"): "a ruling that is unreadable or edits an approved"
    " Plan holds the PR before a conflict is fixed (plan-digest)",
    ("ruling-hold", "first-round"): "a held ruling is answered before a first round",
    ("ruling-hold", "gates"): "a held ruling is answered before the CI gate",
    ("conflict", "first-round"): "a conflict is resolved first (conflict-first)",
    ("conflict", "gates"): "a conflict is a fix at every stage (conflict-first)",
    ("first-round", "gates"): "a PR with no body gets its first round before review",
}

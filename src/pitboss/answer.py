"""The values of a decision and of the answer to what is next (keyword: one-path).

Only ``decide`` makes them; the projections pick from them and the renderers say
them. A decision has an actor, a verb and an item, and no field for a reason not
to act: an item nobody acts on has no value here at all.
"""

import dataclasses
import enum
from typing import Mapping, Sequence


class Actor(enum.Enum):
    """Who acts; the name is the word printed.

    Attributes:
        WORKER: a worker in a slot.
        REVIEWER: a reviewer in a slot, never the author.
        RULING: an Opus agent, no slot.
        ORCHESTRATOR: the orchestrator itself.
        OWNER: the owner.
    """

    WORKER = enum.auto()
    REVIEWER = enum.auto()
    RULING = enum.auto()
    ORCHESTRATOR = enum.auto()
    OWNER = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Decision:
    """Who does what on which item, now.

    Attributes:
        actor: who acts.
        verb: what they do, in words.
        item: the item, ``owner/name#number``.
        title: the item's title.
    """

    actor: Actor
    verb: str
    item: str
    title: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Work:
    """There is work: the decisions, first to take first.

    Attributes:
        first: the first decision.
        rest: the others, in order.
        free: how many slots are free now (a datum, never a filter).
    """

    first: Decision
    rest: Sequence[Decision]
    free: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NotEnoughWork:
    """No item of any priority label can be started: the only empty answer."""


Answer = Work | NotEnoughWork


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Decided:
    """Every decision of one world.

    Attributes:
        answer: what is next.
        by_item: the decision of each examined item that has one.
    """

    answer: Answer
    by_item: Mapping[str, Decision]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class NotFirst:
    """The item the dispatch names is not the head of the order.

    Attributes:
        head: the head of the order.
        named: the item the dispatch named.
    """

    head: Decision
    named: str


DispatchAnswer = Decision | NotFirst | NotEnoughWork

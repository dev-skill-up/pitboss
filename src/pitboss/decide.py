"""The one decider: what is done next, on what, by whom (keyword: one-path).

``decide`` is pure and is the only function that makes a ``Decision`` or an
answer. An item is decided from its own record alone (``decide_item``): it is a
decision when some actor acts on it now, and nothing otherwise. Nothing is said
of an item nobody acts on: no line, no reason, no category (the owner: "JUST.
DONT. MENTION. IT."). The answer to what is next is ``Work`` when there is a
decision, and ``NotEnoughWork`` only when the walk read every page of every
label and no item gave a decision.
"""

import dataclasses
import enum
from typing import Mapping, Sequence, assert_never

from . import steps, world


class Actor(enum.Enum):
    """Who acts; the value is the word printed.

    Attributes:
        WORKER: a worker in a slot.
        REVIEWER: a reviewer in a slot, never the author.
        RULING: an Opus agent, no slot.
        ORCHESTRATOR: the orchestrator itself.
        OWNER: the owner.
    """

    WORKER = "WORKER"
    REVIEWER = "REVIEWER"
    RULING = "RULING"
    ORCHESTRATOR = "ORCHESTRATOR"
    OWNER = "OWNER"


ACTORS: Mapping[steps.Step, Actor] = {
    steps.Step.WORKER: Actor.WORKER,
    steps.Step.SEND_BACK_PLAN_CHECK: Actor.WORKER,
    steps.Step.REGULAR_REVIEW: Actor.REVIEWER,
    steps.Step.OPUS_RULING: Actor.RULING,
    steps.Step.PLAN_EDITED: Actor.RULING,
    steps.Step.UNDRAFT: Actor.ORCHESTRATOR,
    steps.Step.PAUSE_FOR_OWNER: Actor.ORCHESTRATOR,
    steps.Step.FIX_RULING: Actor.ORCHESTRATOR,
    steps.Step.RULING_ESCALATES: Actor.ORCHESTRATOR,
    steps.Step.PLAN_CHECK: Actor.ORCHESTRATOR,
    steps.Step.RUN_E2E: Actor.ORCHESTRATOR,
    steps.Step.MERGE: Actor.ORCHESTRATOR,
}
SLOTTED = frozenset({Actor.WORKER, Actor.REVIEWER})


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
class Decisions:
    """Every decision of one world.

    Attributes:
        answer: what is next.
        by_item: the decision of each examined item that has one.
        records: the record of each item that has a decision.
    """

    answer: Answer
    by_item: Mapping[str, Decision]
    records: Mapping[str, world.Record]


def _pull_decision(record: world.PullRecord) -> Decision | None:
    listed = record.listed
    if record.stuck:  # keyword: stuck-ci: the run is the owner's to re-run
        return Decision(
            actor=Actor.OWNER, verb=record.stuck[0], item=listed.reference, title=listed.title
        )
    step = record.facts.step
    actor = ACTORS.get(step.step)
    loops = step.task is steps.Task.FIX_BLOCKED_BY  # a loop is fixed, not waited on
    if actor is None or (record.blockers and not loops):
        return None
    return Decision(
        actor=actor, verb=steps.describe(step), item=listed.reference, title=listed.title
    )


def _ticket_decision(record: world.TicketRecord) -> Decision | None:
    if record.superseded or record.blockers:
        return None
    return Decision(
        actor=Actor.WORKER,
        verb=steps.FIRST_STEP_READY if record.opens_ready else steps.FIRST_STEP,
        item=record.reference,
        title=record.issue.title,
    )


def decide_item(record: world.Record) -> Decision | None:
    """The decision of one item, from its record alone: the startable predicate.

    Args:
        record: the item and its closure.

    Returns:
        Its decision, or None when nobody acts on it now (it is in no answer).
    """
    match record:
        case world.PullRecord():
            return _pull_decision(record)
        case world.TicketRecord():
            return _ticket_decision(record)
        case world.Kept():
            return None
        case _:  # pragma: no cover
            assert_never(record)


def _decided(
    records: Sequence[world.Record],
) -> tuple[Sequence[Decision], Mapping[str, world.Record]]:
    decided: dict[str, Decision] = {}
    kept: dict[str, world.Record] = {}
    for each in records:
        found = decide_item(each)
        if found is not None:
            decided.setdefault(found.item, found)
            kept.setdefault(found.item, each)
    return list(decided.values()), kept


def decide(made: world.World) -> Decisions:
    """Decide every examined item of a world, and what is next.

    Args:
        made: the world.

    Returns:
        The decisions; ``NotEnoughWork`` only when the walk was exhausted and no
        item gave a decision.
    """
    ordered, records = _decided(made.walk.examined)
    named, named_records = _decided(made.named)
    by_item = {each.item: each for each in [*ordered, *named]}
    answer: Answer
    match made.walk:
        case world.Stopped():
            answer = Work(first=ordered[0], rest=ordered[1:], free=made.free)
        case world.Exhausted():
            if ordered:
                answer = Work(first=ordered[0], rest=ordered[1:], free=made.free)
            else:
                answer = NotEnoughWork()
        case _:  # pragma: no cover
            assert_never(made.walk)
    return Decisions(
        answer=answer, by_item=by_item, records={**named_records, **records}
    )

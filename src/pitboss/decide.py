"""The one decider: what is done next, on what, by whom (keyword: one-path).

``decide`` is pure and is the only function that makes a ``Decision`` or an
answer. An item is decided from its own record alone (``decide_item``): it is a
decision when some actor acts on it now, and nothing otherwise. Nothing is said
of an item no actor takes: no line, no reason, no category (the owner: "JUST.
DONT. MENTION. IT."). The answer to what is next is ``Work`` when there is a
decision, and ``NotEnoughWork`` only when the walk read every page of every
label and no item gave a decision.
"""

import dataclasses
from typing import Mapping, Sequence, assert_never

from . import answer, gate, listed, steps, stepwords, world
from .gatestop import Stop

# who takes each step that has an actor
ACTORS: Mapping[steps.Step, answer.Actor] = {
    steps.Step.WORKER: answer.Actor.WORKER,
    steps.Step.SEND_BACK_PLAN_CHECK: answer.Actor.WORKER,
    steps.Step.REGULAR_REVIEW: answer.Actor.REVIEWER,
    steps.Step.OPUS_RULING: answer.Actor.RULING,
    steps.Step.PLAN_EDITED: answer.Actor.RULING,
    steps.Step.UNDRAFT: answer.Actor.ORCHESTRATOR,
    steps.Step.PAUSE_FOR_OWNER: answer.Actor.ORCHESTRATOR,
    steps.Step.FIX_RULING: answer.Actor.ORCHESTRATOR,
    steps.Step.RULING_ESCALATES: answer.Actor.ORCHESTRATOR,
    steps.Step.PLAN_CHECK: answer.Actor.ORCHESTRATOR,
    steps.Step.RUN_E2E: answer.Actor.ORCHESTRATOR,
    steps.Step.MERGE: answer.Actor.ORCHESTRATOR,
}
SLOTTED = frozenset({answer.Actor.WORKER, answer.Actor.REVIEWER})


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Judgement:
    """What one world decides, with the records the decisions are of.

    Attributes:
        decided: every decision, and what is next.
        records: the record of each item that has a decision (for its brief).
    """

    decided: answer.Decided
    records: Mapping[str, world.Record]


CARRIED: Mapping[steps.Step, answer.Carried] = {  # the gated verb of each step
    steps.Step.MERGE: answer.Carried.MERGE,
    steps.Step.UNDRAFT: answer.Carried.UNDRAFT,
}


def _owner_stuck(record: world.PullRecord) -> answer.Decision:
    # keyword: stuck-ci: the run is the owner's to re-run
    return answer.Decision(
        actor=answer.Actor.OWNER,
        verb=record.stuck[0],
        item=record.row.reference,
        title=record.row.title,
        carried=answer.Carried.NOTHING,
        lifts="",
    )


def _routed(stop: Stop, row: listed.Listed) -> answer.Decision | None:
    # the route of the first stop: the act verdict's rows are rows of the decision
    routed = stop.route.value
    if routed.actor is None:
        return None
    return answer.Decision(
        actor=routed.actor,
        verb=f"{routed.said} ({stop.line})",
        item=row.reference,
        title=row.title,
        carried=answer.Carried.NOTHING,
        lifts=stop.line if routed.lifted else "",
    )


def _stepped(step: steps.Next, row: listed.Listed) -> answer.Decision:
    return answer.Decision(
        actor=ACTORS[step.step],
        verb=stepwords.describe(step),
        item=row.reference,
        title=row.title,
        carried=CARRIED.get(step.step, answer.Carried.NOTHING),
        lifts="",
    )


def _pull_decision(record: world.PullRecord) -> answer.Decision | None:
    if record.held:  # a slot holds it: its agent is at work on it
        return None
    if record.stuck:
        return _owner_stuck(record)
    match record.facts.step:
        case steps.Idle():
            return None  # keyword: one-path: no actor takes an idle PR
        case steps.Next() as step:
            return _at_step(record, step)
        case _:  # pragma: no cover
            assert_never(record.facts.step)


def _at_step(record: world.PullRecord, step: steps.Next) -> answer.Decision | None:
    loops = step.task is steps.Task.FIX_BLOCKED_BY  # a loop is fixed, not waited on
    if step.step not in ACTORS or (record.blockers and not loops):
        return None
    stopped = gate.stops_of(step.step, record.gated) if record.gated else ()
    if stopped:
        return _routed(stopped[0], record.row)
    return _stepped(step, record.row)


def _ticket_decision(record: world.TicketRecord) -> answer.Decision | None:
    if record.superseded or record.blockers:
        return None
    return answer.Decision(
        actor=answer.Actor.WORKER,
        verb=steps.FIRST_STEP_READY if record.opens_ready else steps.FIRST_STEP,
        item=record.reference,
        title=record.issue.title,
        carried=answer.Carried.NOTHING,
        lifts="",
    )


def decide_item(record: world.Record) -> answer.Decision | None:
    """The decision of one item, from its record alone: the startable predicate.

    Args:
        record: the item and its closure.

    Returns:
        Its decision, or None when no actor takes it now (it is in no answer).
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
) -> tuple[Sequence[answer.Decision], Mapping[str, world.Record]]:
    decided: dict[str, answer.Decision] = {}
    kept: dict[str, world.Record] = {}
    for each in records:
        found = decide_item(each)
        if found is not None:
            decided.setdefault(found.item, found)
            kept.setdefault(found.item, each)
    return list(decided.values()), kept


def _answer(
    walk: world.Walk, ordered: Sequence[answer.Decision], free: int
) -> answer.Answer:
    match walk:
        case world.Exhausted() if not ordered:  # every page read, nothing startable
            return answer.NotEnoughWork()
        case world.Stopped() | world.Exhausted():
            return answer.Work(first=ordered[0], rest=ordered[1:], free=free)
        case _:  # pragma: no cover
            assert_never(walk)


def decide(made: world.World) -> Judgement:
    """Decide every examined item of a world, and what is next.

    Args:
        made: the world.

    Returns:
        The decisions; ``NotEnoughWork`` only when the walk was exhausted and no
        item gave a decision.
    """
    ordered, records = _decided(made.walk.examined)
    named, named_records = _decided(made.named)
    decided = answer.Decided(
        answer=_answer(made.walk, ordered, made.free),
        by_item={each.item: each for each in [*ordered, *named]},
    )
    return Judgement(decided=decided, records={**named_records, **records})

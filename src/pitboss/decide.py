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
from typing import AbstractSet, Mapping, Sequence, assert_never

from . import actdecide, answer, blockedstep, finishstep, flowstep
from . import gate, holds, listed, pullfacts, sharedstep, slotbook, steps
from . import stepwords, stuckwords, work, world
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
# the actors an agent is started and briefed for
BRIEFED = frozenset({answer.Actor.WORKER, answer.Actor.REVIEWER, answer.Actor.RULING})


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
        verb=stuckwords.warning(record.stuck[0]),
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


def facts_of(record: world.PullRecord) -> pullfacts.PullFacts:
    """A PR's facts at the step its flow, blockers, shared red and hand-back give.

    The flow's rows and the three settlers are rows of the decision (the one-path
    plan, 6.1), on what the record holds: no read is made here.

    Args:
        record: the record, as read.

    Returns:
        Its facts at its settled step.
    """
    facts = flowstep.at_flow(record.facts)
    blocked = blockedstep.step_of(facts, record.blocked_by) or facts.step
    at = dataclasses.replace(facts, step=blocked)
    moved = sharedstep.stepped(at, record.shared) or blocked
    shared = dataclasses.replace(facts, step=moved)
    finished = finishstep.step_of(shared) or shared.step
    return dataclasses.replace(shared, step=finished)


def _pull_decision(record: world.PullRecord) -> answer.Decision | None:
    step = facts_of(record).step
    match step:
        case steps.Idle() if record.stuck:
            return _owner_stuck(record)
        case steps.Idle():
            return None  # keyword: one-path: no actor takes an idle PR
        case steps.Next():
            return _at_step(record, step)
        case _:  # pragma: no cover
            assert_never(step)


def _at_step(record: world.PullRecord, step: steps.Next) -> answer.Decision | None:
    loops = step.task is steps.Task.FIX_BLOCKED_BY  # a loop is fixed, not waited on
    if step.step not in ACTORS or (world.blockers_of(record) and not loops):
        return None
    stopped = gate.stops_of(step.step, record.gated) if record.gated else ()
    if stopped:
        return _routed(stopped[0], record.row)
    return _stepped(step, record.row)


def starts(decided: answer.Decision, records: Mapping[str, world.Record]) -> bool:
    """Whether an agent starts for a decision, and so gets a brief.

    Args:
        decided: the decision.
        records: the record of each decided item.

    Returns:
        True for a decision of an actor that is briefed, but a pull request of no
        round (a refused Plan check, sent back by the worker that pushed it) that
        is not an Opus ruling.
    """
    if decided.actor not in BRIEFED:
        return False
    found = records[decided.item]
    if isinstance(found, world.PullRecord) and decided.actor is not answer.Actor.RULING:
        return work.category_of(facts_of(found)) is not None
    return True


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
        case world.Occupied():
            return None
        case _:  # pragma: no cover
            assert_never(record)


def _slotted(book: slotbook.Ledger) -> AbstractSet[str]:
    # the items a slot's agent works on
    return frozenset(slot.task for slot in book.slots if slot.agent)


def pull_kept(grounds: world.Grounds, reference: str) -> bool:
    """Whether the grounds alone say no actor takes a pull request (plan 3.1(3)).

    Args:
        grounds: the listing, the ledger and the holds.
        reference: the pull request, ``owner/name#number``.

    Returns:
        True when a slot holds it.
    """
    return reference in _slotted(grounds.book)


def ticket_kept(grounds: world.Grounds, reference: str) -> bool:
    """Whether the grounds alone say no actor takes a ticket (plan 3.1(3)).

    Args:
        grounds: the listing, the ledger and the holds.
        reference: the ticket, ``owner/name#number``.

    Returns:
        True when a slot holds it, an open pull request works on it (keyword:
        taken), or the owner's hold or the quiesce covers its repository.
    """
    if pull_kept(grounds, reference):
        return True
    if any(reference in row.works_on for row in grounds.listing):
        return True
    opened = [row.repo.slug for row in grounds.listing]
    standing = holds.standing(grounds.holds, opened)
    return grounds.quiesced or reference.rpartition("#")[0] in standing


def decide_in(grounds: world.Grounds, record: world.Record) -> answer.Decision | None:
    """The startable predicate: the grounds' occupancy, then the item's own record.

    Args:
        grounds: the listing, the ledger and the holds.
        record: the item and its closure.

    Returns:
        Its decision, or None when no actor takes it now.
    """
    match record:
        case world.PullRecord():
            occupied = pull_kept(grounds, record.row.reference)
        case world.TicketRecord():
            taken = record.reference in record.branch_named
            occupied = ticket_kept(grounds, record.reference) or taken
        case world.Occupied():
            occupied = True
        case _:  # pragma: no cover
            assert_never(record)
    return None if occupied else decide_item(record)


def _decided(
    grounds: world.Grounds, records: Sequence[world.Record]
) -> tuple[Sequence[answer.Decision], Mapping[str, world.Record]]:
    decided: dict[str, answer.Decision] = {}
    held: dict[str, world.Record] = {}
    for each in records:
        found = decide_in(grounds, each)
        if found is not None:
            decided.setdefault(found.item, found)
            held.setdefault(found.item, each)
    return list(decided.values()), held


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
    grounds = made.grounds
    ordered, records = _decided(grounds, made.walk.examined)
    named, named_records = _decided(grounds, made.named)
    free = sum(1 for slot in grounds.book.slots if not slot.agent)
    decided = answer.Decided(
        answer=_answer(made.walk, ordered, free),
        by_item={each.item: each for each in [*ordered, *named]},
        acting=actdecide.verdict(made.act, grounds.held, actdecide.ROWS),
    )
    return Judgement(decided=decided, records={**named_records, **records})

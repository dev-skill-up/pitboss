"""The one decider on hand-made worlds (keyword: one-path)."""

import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to, instance_of

from .. import answer, decide, shapes, slotbook, steps, world

BOOK = slotbook.ledger_of([])


def ticket(number: int, **changes: bool) -> world.TicketRecord:
    """A p2 ticket of ``o/r``, as the walk reads it.

    Args:
        number: its number.
        **changes: ``superseded`` or ``blocked``.

    Returns:
        Its record.
    """
    issue = shapes.Issue(
        number=number,
        title=f"ticket {number}",
        created_at="2026-11-01T00:00:00Z",
        labels=frozenset({"p2"}),
        body="",
        comments=0,
    )
    return world.TicketRecord(
        reference=f"o/r#{number}",
        issue=issue,
        priority=2,
        superseded=changes.get("superseded", False),
        blockers=["o/r#99"] if changes.get("blocked", False) else [],
        opens_ready=False,
    )


def decision_of(number: int) -> answer.Decision:
    """The decision the one decider makes for a startable ticket of ``o/r``.

    Args:
        number: its number.

    Returns:
        The decision.
    """
    return answer.Decision(
        actor=answer.Actor.WORKER,
        verb=steps.FIRST_STEP,
        item=f"o/r#{number}",
        title=f"ticket {number}",
        carried=answer.Carried.NOTHING,
        lifts="",
    )


def work_of(numbers: Sequence[int]) -> answer.Work:
    """The work of startable tickets of ``o/r``, in order, with one free slot.

    Args:
        numbers: their numbers.

    Returns:
        The work.
    """
    every = [decision_of(n) for n in numbers]
    return answer.Work(first=every[0], rest=every[1:], free=1)


def _world(walk: world.Walk) -> world.World:
    return world.World(listing=[], walk=walk, named=[], book=BOOK, free=1)


def answer_of(walk: world.Walk) -> answer.Answer:
    """What the one decider answers for a walk.

    Args:
        walk: the walk.

    Returns:
        The answer.
    """
    return decide.decide(_world(walk)).decided.answer


class TestNotEnoughWork(unittest.TestCase):
    """``NotEnoughWork`` only when every page was read and nothing can start."""

    def test_everything_waiting_is_not_enough_work(self) -> None:
        """Taken, held, slot-held, blocked and superseded items give no decision."""
        examined: list[world.Record] = [
            world.Kept(reference="o/r#1", by=world.Keeper.PULL),
            world.Kept(reference="o/r#2", by=world.Keeper.HOLD),
            world.Kept(reference="o/r#3", by=world.Keeper.SLOT),
            ticket(4, blocked=True),
            ticket(5, superseded=True),
        ]
        found = decide.decide(_world(world.Exhausted(examined=examined)))
        assert_that(found.decided.answer, instance_of(answer.NotEnoughWork))
        assert_that(found.decided.by_item, equal_to({}))

    def test_b2_a_blocked_ticket_is_skipped_and_a_startable_one_is_work(self) -> None:
        """One startable p2 ticket after the waiting ones is the work, named."""
        examined: list[world.Record] = [ticket(4, blocked=True), ticket(6)]
        given = answer_of(world.Exhausted(examined=examined))
        assert_that(given, equal_to(work_of([6])))

    def test_a_stopped_walk_is_work(self) -> None:
        """A walk that reached its stop answers its decisions, in order."""
        examined: list[world.Record] = [ticket(n) for n in range(1, 6)]
        given = answer_of(world.Stopped(examined=examined, stop=5))
        assert_that(given, equal_to(work_of([1, 2, 3, 4, 5])))

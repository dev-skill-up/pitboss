"""The one decider on hand-made worlds (keyword: one-path)."""

import unittest

from hamcrest import assert_that, equal_to, instance_of

from .. import answer, decide, ledger, shapes, steps, world

BOOK = ledger.Ledger(slots=[], failed={})


def _ticket(number: int, **changes: bool) -> world.TicketRecord:
    issue = shapes.Issue(
        number=number,
        title=f"ticket {number}",
        created_at="2026-11-01T00:00:00Z",
        labels=frozenset({"p2"}),
        body="",
    )
    return world.TicketRecord(
        reference=f"o/r#{number}",
        issue=issue,
        priority=2,
        superseded=changes.get("superseded", False),
        blockers=["o/r#99"] if changes.get("blocked", False) else [],
        opens_ready=False,
    )


def _decision(number: int) -> answer.Decision:
    return answer.Decision(
        actor=answer.Actor.WORKER,
        verb=steps.FIRST_STEP,
        item=f"o/r#{number}",
        title=f"ticket {number}",
    )


def _work(numbers: list[int]) -> answer.Work:
    every = [_decision(n) for n in numbers]
    return answer.Work(first=every[0], rest=every[1:], free=1)


def _world(walk: world.Walk) -> world.World:
    return world.World(listing=[], walk=walk, named=[], book=BOOK, free=1)


def _answer(walk: world.Walk) -> answer.Answer:
    return decide.decide(_world(walk)).decided.answer


class TestNotEnoughWork(unittest.TestCase):
    """``NotEnoughWork`` only when every page was read and nothing can start."""

    def test_everything_waiting_is_not_enough_work(self) -> None:
        """Taken, held, slot-held, blocked and superseded items give no decision."""
        examined: list[world.Record] = [
            world.Kept(reference="o/r#1", by=world.Keeper.PULL),
            world.Kept(reference="o/r#2", by=world.Keeper.HOLD),
            world.Kept(reference="o/r#3", by=world.Keeper.SLOT),
            _ticket(4, blocked=True),
            _ticket(5, superseded=True),
        ]
        found = decide.decide(_world(world.Exhausted(examined=examined)))
        assert_that(found.decided.answer, instance_of(answer.NotEnoughWork))
        assert_that(found.decided.by_item, equal_to({}))

    def test_a_startable_ticket_on_a_last_page_is_work(self) -> None:
        """One startable p2 ticket after the waiting ones is the work, named."""
        examined: list[world.Record] = [_ticket(4, blocked=True), _ticket(6)]
        given = _answer(world.Exhausted(examined=examined))
        assert_that(given, equal_to(_work([6])))

    def test_a_stopped_walk_is_work(self) -> None:
        """A walk that reached its stop answers its decisions, in order."""
        examined: list[world.Record] = [_ticket(n) for n in range(1, 6)]
        given = _answer(world.Stopped(examined=examined, stop=5))
        assert_that(given, equal_to(_work([1, 2, 3, 4, 5])))

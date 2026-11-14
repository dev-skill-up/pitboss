"""The one decider on hand-made worlds (keyword: one-path).

Plan part: 6.2 and 6.5 (the pure decide on hand-made worlds; NotEnoughWork).
"""

import dataclasses
import unittest
from typing import Sequence

from hamcrest import assert_that, equal_to, instance_of

from .. import actfacts, answer, config, decide, holdconfig, listed, shapes, slotbook
from .. import steps, world
from . import fakes

BOOK = slotbook.ledger_of([])
GROUNDS = world.Grounds(
    listing=[], book=BOOK, holds=holdconfig.NONE, held={}, quiesced=False
)


def ticket(number: int, **changes: bool) -> world.TicketRecord:
    """A p2 ticket of ``o/r``, as the walk reads it.

    Args:
        number: its number.
        **changes: ``superseded``, ``blocked`` or ``taken`` (a branch names it).

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
        branch_named={f"o/r#{number}"} if changes.get("taken", False) else set(),
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
    book = slotbook.ledger_of([slotbook.empty_slot("s1", "m")])
    grounds = dataclasses.replace(GROUNDS, book=book)
    return world.World(
        grounds=grounds, walk=walk, named=[], act=actfacts.NO_ACT, forced=()
    )


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

    def test_6_2_everything_waiting_is_not_enough_work(self) -> None:
        """Occupied, branch-taken, blocked and superseded items give no decision."""
        examined: list[world.Record] = [
            world.Occupied(reference="o/r#1", pull=False),
            world.Occupied(reference="o/r#2", pull=True),
            ticket(3, taken=True),
            ticket(4, blocked=True),
            ticket(5, superseded=True),
        ]
        found = decide.decide(_world(world.Exhausted(examined=examined)))
        assert_that(found.decided.answer, instance_of(answer.NotEnoughWork))
        assert_that(found.decided.by_item, equal_to({}))

    def test_6_2_b2_a_blocked_ticket_is_skipped_a_startable_one_is_work(self) -> None:
        """One startable p2 ticket after the waiting ones is the work, named."""
        examined: list[world.Record] = [ticket(4, blocked=True), ticket(6)]
        given = answer_of(world.Exhausted(examined=examined))
        assert_that(given, equal_to(work_of([6])))

    def test_6_2_a_stopped_walk_is_work(self) -> None:
        """A walk that reached its stop answers its decisions, in order."""
        examined: list[world.Record] = [ticket(n) for n in range(1, 6)]
        given = answer_of(world.Stopped(examined=examined, stop=5))
        assert_that(given, equal_to(work_of([1, 2, 3, 4, 5])))


def slotted(task: str) -> world.Grounds:
    """Grounds with one slot whose agent works on an item.

    Args:
        task: the item.

    Returns:
        The grounds.
    """
    slot = dataclasses.replace(slotbook.empty_slot("s1", "m"), agent="a")
    book = slotbook.ledger_of([dataclasses.replace(slot, task=task)])
    return dataclasses.replace(GROUNDS, book=book)


class TestKept(unittest.TestCase):
    """Plan 3.1(3): the grounds alone say no actor takes an item."""

    def test_3_1_a_slot_keeps_its_item(self) -> None:
        """An item a slot's agent works on is kept, a pull request too."""
        grounds = slotted("o/r#1")
        kinds = (decide.pull_kept, decide.ticket_kept)
        found = [each(grounds, "o/r#1") for each in kinds]
        assert_that(found, equal_to([True, True]))

    def test_3_1_a_pull_request_no_slot_holds_is_read(self) -> None:
        """A quiesce keeps tickets only."""
        quiet = dataclasses.replace(GROUNDS, quiesced=True)
        assert_that(decide.pull_kept(quiet, "o/r#1"), equal_to(False))

    def test_3_1_a_quiesce_a_hold_or_a_pull_request_keeps_a_ticket(self) -> None:
        """The owner's quiesce, a hold of its repository, a PR that works on it."""
        holds = holdconfig.Holds(new_pull_requests=frozenset({"o/r"}), max_open=-1)
        row = listed.listed_row(config.make_repo("o", "r"), "", fakes.pull_body(3))
        working = dataclasses.replace(row, works_on=frozenset({"o/r#1"}))
        listing = dataclasses.replace(GROUNDS, listing=[working])
        found = [
            decide.ticket_kept(listing, "o/r#1"),
            decide.ticket_kept(dataclasses.replace(GROUNDS, quiesced=True), "o/r#1"),
            decide.ticket_kept(dataclasses.replace(GROUNDS, holds=holds), "o/r#1"),
            decide.ticket_kept(GROUNDS, "o/r#1"),
        ]
        assert_that(found, equal_to([True, True, True, False]))

    def test_3_1_an_occupied_item_has_no_decision(self) -> None:
        """``decide_in`` of an item the walk did not read is nothing."""
        occupied = world.Occupied(reference="o/r#1", pull=False)
        assert_that(decide.decide_in(GROUNDS, occupied), equal_to(None))

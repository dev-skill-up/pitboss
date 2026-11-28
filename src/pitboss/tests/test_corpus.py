"""The recorded PRs of the queue: each gets a step whose own work ends it (#526).

``corpus/`` holds what ``pitboss next`` read of every open PR of bats-lang on
2026-11-24. For dom#140, quire#1125, #1128 and #1130 the record also holds ``was``,
the task the decider gave them, a dead end. quire-1128-flake is quire#1128 at
a second head, whose red an open p0 ticket owns (``waits``, pitboss#531);
quire-1127-miss is quire#1127, whose red repository-prototype's allowlist fixes and
nothing open asks for (``outside``).
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to, has_length, is_not

from .. import flow, flowstep, steps, workerselect
from .. import witnesses
from . import corpusreplay

DEAD_ENDS = ("dom-140", "quire-1125", "quire-1128", "quire-1130")
OWNED = "quire-1128-flake"
OUTSIDE = "quire-1127-miss"


def step_name(record: Mapping[str, object]) -> Mapping[str, object]:
    """The step a record says its PR gets.

    Args:
        record: the record.

    Returns:
        ``{"step": ..., "task": ...}``.
    """
    expected = record["expected"]
    return expected if isinstance(expected, dict) else {}


class TestCorpus(unittest.TestCase):
    """Every recorded PR, replayed through the shipped reader and flow."""

    def test_the_corpus_is_every_pr_it_names(self) -> None:
        """39 open PRs of the queue and quire#1128 and quire#1127 at a second head."""
        assert_that(corpusreplay.names(), has_length(41))

    def test_each_pr_gets_the_step_recorded_for_it(self) -> None:
        """The reads replayed give the recorded step and task."""
        for name in corpusreplay.names():
            record = corpusreplay.load(name)
            found = flowstep.at_flow(corpusreplay.read(record)).step
            assert isinstance(found, steps.Next)
            task = found.task.name if found.task else ""
            assert_that(
                (name, found.step.name, task),
                equal_to((name, step_name(record)["step"], step_name(record)["task"])),
            )

    def test_the_work_of_each_worker_step_changes_what_it_was_decided_from(
        self,
    ) -> None:
        """Do what its task requires to the PR: the flow gives another step."""
        writes = {workerselect.Effect.EDIT_BODY, workerselect.Effect.EDIT_PLAN}
        states = {
            name: corpusreplay.read(corpusreplay.load(name)).state
            for name in corpusreplay.names()
        }
        found = {name: flow.next_step(state) for name, state in states.items()}
        # a body or a Plan the worker writes is not in a record
        worked = [
            (name, state, step)
            for (name, state), step in zip(states.items(), found.values())
            if isinstance(step, steps.Next)
            and step.task is not None
            and not workerselect.TABLE[step.task].required & writes
        ]
        after = [
            (name, flow.next_step(witnesses.applied(state, step.task)), step)
            for name, state, step in worked
            if step.task is not None
        ]
        assert_that(all(each[1] != each[2] for each in after), equal_to(True))
        assert_that(len(after) > 3, equal_to(True))

    def test_the_old_dead_ends_have_another_step_now(self) -> None:
        """The dead ends were sent to a step no edit ends."""
        for name in DEAD_ENDS:
            record = corpusreplay.load(name)
            assert_that(record["recorded_dead_end"], equal_to(True))
            was = record["was"]
            assert_that(was is not None, equal_to(True))
            assert_that(step_name(record)["task"], is_not(equal_to(was)))

    def test_a_red_status_about_the_review_is_the_reviews_stop(self) -> None:
        """quire#1130: the merge's first stop is the review's, so ``act review``."""
        record = corpusreplay.load("quire-1130")
        found = corpusreplay.first_stop(record)
        assert_that((found, record["gate"]), equal_to(("REVIEW", "REVIEW")))

    def test_a_red_an_open_ticket_names_is_that_tickets(self) -> None:
        """quire#1128's red is the flake of quire#1137: the PR waits for it."""
        record = corpusreplay.load(OWNED)
        assert_that(record["recorded_dead_end"], equal_to(True))
        found = corpusreplay.owners(record)
        assert_that(list(found), equal_to(["bats-lang/quire#1137"]))
        assert_that(list(found), equal_to(record["waits"]))

    def test_a_red_whose_fix_is_outside_and_unowned_is_a_ticket_to_file(self) -> None:
        """quire#1127: a canonical-files miss no open item asks for is a group."""
        record = corpusreplay.load(OUTSIDE)
        assert_that(record["recorded_dead_end"], equal_to(True))
        found = corpusreplay.outside(record)
        assert_that(list(found), has_length(1))
        assert_that(list(found), equal_to(record["outside"]))

    def test_a_task_the_corpus_cannot_do_is_a_ticket(self) -> None:
        """Filing a ticket changes nothing the flow reads."""
        state = corpusreplay.read(corpusreplay.load("quire-1130")).state
        ticket = workerselect.OUTSIDE
        done = witnesses.applied(state, workerselect.Task.SHARED_RED, None, ticket)
        assert_that(done, equal_to(state))

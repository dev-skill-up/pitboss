"""The recorded PRs of the queue: each gets a step whose own work ends it (pitboss#526).

``corpus/`` holds what ``pitboss next`` read of every open PR of bats-lang on
2026-11-24 (and of dom#140 and quire#1128, whose old steps were dead
ends: ``was`` is the step the decider of 8a36af1 gave them).
"""

import unittest
from typing import Mapping

from hamcrest import assert_that, equal_to, has_length, is_not

from .. import flow, flowstep, steps, workerselect
from . import corpuseffects, corpusreplay

DEAD_ENDS = ("dom-140", "quire-1128")


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
        """39 open PRs of the queue, each with its reads."""
        assert_that(corpusreplay.names(), has_length(39))

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
        checked = 0
        for name in corpusreplay.names():
            state = corpusreplay.read(corpusreplay.load(name)).state
            found = flow.next_step(state)
            if not isinstance(found, steps.Next) or found.task is None:
                continue
            after = corpuseffects.applied(state, found.task)
            if after is not None:
                checked += 1
                assert_that(
                    (name, flow.next_step(after)), is_not(equal_to((name, found)))
                )
        assert_that(checked > 3, equal_to(True))

    def test_the_old_dead_ends_have_another_step_now(self) -> None:
        """dom#140 and quire#1128 were sent to a worker no edit could end."""
        for name in DEAD_ENDS:
            record = corpusreplay.load(name)
            assert_that(record["recorded_dead_end"], equal_to(True))
            was = record["was"]
            assert_that(was is not None, equal_to(True))
            assert_that(step_name(record)["task"], is_not(equal_to(was)))

    def test_a_task_the_corpus_cannot_do_is_a_ticket(self) -> None:
        """Filing a ticket changes nothing the flow reads."""
        state = corpusreplay.read(corpusreplay.load("quire-1130")).state
        assert_that(
            corpuseffects.applied(state, workerselect.Task.SHARED_RED), equal_to(None)
        )

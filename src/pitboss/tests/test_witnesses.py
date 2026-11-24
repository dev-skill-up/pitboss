"""Every worker task has a PR the decider gives it and a next step after its effects.

pitboss#526 (keyword: progress, witnesses): the task table is total, and for each
task the shipped decider, run on a PR it chooses the task at and on the same PR after
the worker's required effects, gives another step. The 50846 states of the walk
(``test_properties``) are the same property over every state of the model; these are
the states the model's events do not reach (a body gone stale, a Blocked-by line, a
shared red).
"""

import unittest

from hamcrest import assert_that, equal_to

from .. import steps, workerselect
from . import witnesses


def _task_of(step: steps.Move | None) -> workerselect.Task | None:
    return step.task if isinstance(step, steps.Next) else None


class TestWitnesses(unittest.TestCase):
    """What the decider does at each task's witness."""

    def test_every_task_has_a_witness(self) -> None:
        """The two tables name the same tasks."""
        assert_that(set(witnesses.WITNESSES), equal_to(set(workerselect.TABLE)))

    def test_the_decider_chooses_the_task_at_its_witness(self) -> None:
        """A witness that gives another step proves nothing about the task."""
        for task, each in witnesses.WITNESSES.items():
            with self.subTest(task=task.name):
                assert_that(_task_of(each.before()), equal_to(task))

    def test_the_effects_the_table_requires_give_another_step(self) -> None:
        """The step decided from what the worker changed is not the same task."""
        for task, each in witnesses.WITNESSES.items():
            with self.subTest(task=task.name):
                after = each.after()
                assert_that(_task_of(after) is task, equal_to(False))

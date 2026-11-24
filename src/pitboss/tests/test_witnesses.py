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

from .. import proofseeds, steps, witnesses, witnessstates, workerselect


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
                assert_that(
                    _task_of(proofseeds.shipped_step(each.before)), equal_to(task)
                )

    def test_the_effects_the_table_requires_move_the_pr_to_no_worker(self) -> None:
        """The step decided from what the worker changed is no worker's."""
        for task, each in witnesses.WITNESSES.items():
            with self.subTest(task=task.name):
                assert_that(
                    witnesses.stuck(each, proofseeds.shipped_step), equal_to(False)
                )

    def test_a_worker_that_does_nothing_leaves_every_task_where_it_was(self) -> None:
        """With no effect the task is chosen again: the witnesses read the table."""
        for task in workerselect.TABLE:
            with self.subTest(task=task.name):
                bare = witnesses.of(task, frozenset())
                assert_that(
                    proofseeds.shipped_step(bare.after),
                    equal_to(proofseeds.shipped_step(bare.before)),
                )
                assert_that(
                    witnesses.stuck(bare, proofseeds.shipped_step), equal_to(True)
                )

    def test_the_step_after_may_not_be_none_or_another_worker(self) -> None:
        """A step that is none, or another worker's, is stuck."""
        here = witnesses.Setting(pr=witnessstates.state(), known={}, groups=())
        none = witnesses.Witness(before=here, after=here)
        moved = witnesses.Witness(before=here, after=here)
        steps_of = iter(
            [None, None, steps.worker(workerselect.Task.RUN_PLAN)]
            + [steps.worker(workerselect.Task.FIX_CI)] * 2
        )

        def decided(setting: witnesses.Setting) -> steps.Move | None:
            return next(steps_of)

        assert_that(witnesses.stuck(none, decided), equal_to(True))
        assert_that(witnesses.stuck(moved, decided), equal_to(True))

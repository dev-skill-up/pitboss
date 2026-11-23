"""A step's task has a category, a kind and a text (keyword: standing, #524).

quire#1128: the sweep said ``hand this head and body back`` and the saved brief said
``fix the findings of the review``, because a task with no category fell to a default.
"""

import unittest

from hamcrest import assert_that, equal_to

from .. import brieftextwork, steps, suggestkind, work, workitem


class TestEveryTaskIsTold(unittest.TestCase):
    """No task falls to a default."""

    def test_each_task_has_a_category(self) -> None:
        """The map names every task."""
        missing = [each for each in steps.Task if each not in work.CATEGORY_OF_TASK]
        assert_that(missing, equal_to([]))

    def test_each_category_a_task_gives_has_a_kind_and_a_text(self) -> None:
        """A category's kind is told in a brief of its own."""
        kinds = [
            suggestkind.OF_CATEGORY[each] for each in work.CATEGORY_OF_TASK.values()
        ]
        untold = [each for each in kinds if each not in brieftextwork.TASKS]
        assert_that(untold, equal_to([]))

    def test_the_hand_back_step_is_not_the_fix_the_review_brief(self) -> None:
        """The case of quire#1128."""
        found = work.CATEGORY_OF_TASK[steps.Task.HAND_BACK]
        assert_that(found, equal_to(workitem.Category.HAND_BACK))

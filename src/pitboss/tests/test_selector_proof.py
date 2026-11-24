"""P13.3 refuses a table with a task that cannot end its own selection."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import proofseeds, proofsource, selectorproofs, steps, workerselect
from ..proofcase import Seed

ROOT = pathlib.Path(workerselect.__file__).parents[2]
TEXTS = proofsource.read(ROOT)
OTHER = "\nOTHER = steps.Next(\n    step=steps.Step.WORKER, task=steps.Task.FIX_CI\n)\n"


def found(seed: Seed) -> str:
    """What P13.3 says of the package with one seed.

    Args:
        seed: the edit.

    Returns:
        Its findings, one for each line.
    """
    package = proofsource.of_texts(proofseeds.seeded(TEXTS, seed))
    return "\n".join(selectorproofs.tasks_can_end_their_selection(package))


class TestSelectorProof(unittest.TestCase):
    """What the table, as written, may not say."""

    def test_the_table_as_written_has_no_finding(self) -> None:
        """Every task has one entry that requires an effect."""
        package = proofsource.of_texts(TEXTS)
        assert_that(
            selectorproofs.tasks_can_end_their_selection(package), has_length(0)
        )

    def test_a_task_that_requires_no_effect_is_refused(self) -> None:
        """A task whose worker may do nothing that ends it."""
        said = found(
            Seed(
                path="workerselect.py",
                old="_of(Task.REFRESH_BODY, BODY_ONLY, BODY_ONLY)",
                new="_of(Task.REFRESH_BODY, frozenset(), BODY_ONLY)",
            )
        )
        assert_that(said, contains_string("Task.REFRESH_BODY requires no effect"))

    def test_a_task_with_no_entry_is_refused(self) -> None:
        """Dropping the entry of HAND_BACK."""
        said = found(
            Seed(
                path="workerselect.py",
                old="        _of(Task.HAND_BACK, BACK, BACK),\n",
                new="",
            )
        )
        assert_that(said, contains_string("Task.HAND_BACK has 0 entries"))

    def test_a_brief_with_a_list_of_its_own_is_refused(self) -> None:
        """The push-less list the table replaced."""
        said = found(
            Seed(
                path="brief.py",
                old="def _push_lines",
                new="PUSHLESS = {}\n\n\ndef _push_lines",
            )
        )
        assert_that(said, contains_string("brief keeps its own push-less list"))

    def test_a_brief_that_ignores_the_table_is_refused(self) -> None:
        """The table is the source of the sentences."""
        said = found(
            Seed(
                path="brief.py",
                old="in workerselect.TABLE.items()",
                new="in {}.items()",
            )
        )
        assert_that(said, contains_string("brief does not read workerselect.TABLE"))

    def test_a_missing_table_is_a_finding(self) -> None:
        """A package with no workerselect."""
        package = proofsource.of_texts(
            {k: v for k, v in TEXTS.items() if "workerselect" not in k}
        )
        assert_that(
            selectorproofs.tasks_can_end_their_selection(package),
            equal_to(["P13.3: the table of worker tasks is missing"]),
        )

    def test_a_worker_built_outside_the_table_is_refused(self) -> None:
        """A site that calls steps.worker itself."""
        said = found(
            Seed(
                path="conflicts.py",
                old="",
                new=OTHER,
            )
        )
        assert_that(said, contains_string("conflicts:"))
        assert_that(said, equal_to(said.strip()))

    def test_the_table_builds_what_steps_builds(self) -> None:
        """A table's worker is the step of its task."""
        for task, entry in workerselect.TABLE.items():
            assert_that(steps.worker(task).task, equal_to(entry.task))

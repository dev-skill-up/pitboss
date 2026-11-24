"""P13.3 refuses a table with a task that cannot end its own selection."""

import pathlib
import unittest

from hamcrest import assert_that, contains_string, equal_to, has_length

from .. import proofseeds, proofsource, selectorproofs, steps, workerselect
from ..proofcase import Seed

ROOT = pathlib.Path(workerselect.__file__).resolve().parents[2]
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
        """Every task reads a fact its action writes."""
        package = proofsource.of_texts(TEXTS)
        assert_that(
            selectorproofs.tasks_can_end_their_selection(package), has_length(0)
        )

    def test_a_task_that_reads_nothing_it_writes_is_refused(self) -> None:
        """A task selected by CI whose action changes the body."""
        said = found(
            Seed(
                path="workerselect.py",
                old="_of(Task.FIX_CI, {Fact.CHECKS}, PUSH)",
                new="_of(Task.FIX_CI, {Fact.CHECKS}, EDIT - {Fact.REVIEWS})",
            )
        )
        assert_that(said, contains_string("Task.FIX_CI reads no fact"))

    def test_a_text_with_nothing_to_end_it_is_refused(self) -> None:
        """dom#140: the ruling's words, and no review that ends them."""
        said = found(
            Seed(path="workerselect.py", old="            Fact.REVIEWS,\n", new="")
        )
        assert_that(said, contains_string("Task.RULING_STEPS reads text"))

    def test_a_task_with_no_entry_is_refused(self) -> None:
        """Dropping the entry of HAND_BACK."""
        said = found(
            Seed(
                path="workerselect.py",
                old="        _of(Task.HAND_BACK, {Fact.HANDBACK}, "
                "frozenset({Fact.HANDBACK})),\n",
                new="",
            )
        )
        assert_that(said, contains_string("Task.HAND_BACK has 0 entries"))

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

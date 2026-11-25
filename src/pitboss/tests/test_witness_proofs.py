"""Tests of P13.4 (``witnessproofs``), which ``proofseeds`` runs with the proofs."""

import functools
import pathlib
import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to, has_length, starts_with

from .. import proofseeds, proofsource, witnessproofs, workerselect
from ..proofcase import Seed

CASES = witnessproofs.cases(proofseeds.shipped_step)


@functools.cache
def package_texts() -> Mapping[str, str]:
    """The sources of the package, read once.

    Returns:
        Each file's text, by its path from the root.
    """
    return proofsource.read(pathlib.Path(proofsource.__file__).parent.parent.parent)


def said(task: str, seed: Seed | None = None) -> str:
    """What P13.4 says of a task in the package, seeded or not.

    Args:
        task: the task.
        seed: the edit, none for the package as written.

    Returns:
        Its findings, one for each line.
    """
    texts = proofseeds.seeded(package_texts(), seed) if seed else package_texts()
    package = proofsource.of_texts(texts)
    return "\n".join(witnessproofs.progress_of(task, proofseeds.shipped_step)(package))


class TestWitnessProofs(unittest.TestCase):
    """What the effects of a table entry must do to the PR."""

    def test_the_table_as_written_has_no_finding(self) -> None:
        """Every task's effects move its PR to no worker."""
        for task in workerselect.Task:
            with self.subTest(task=task.name):
                assert_that(said(task.name), equal_to(""))

    def test_an_effect_the_step_is_not_decided_from_is_refused(self) -> None:
        """A red check is not ended by handing back an unchanged head."""
        found = said(
            "FIX_CI",
            Seed(
                path="workerselect.py",
                old="_of(Task.FIX_CI, PUSH_THEN_BACK, PUSHES)",
                new="_of(Task.FIX_CI, BACK, PUSHES)",
            ),
        )
        assert_that(found, contains_string("P13.4.FIX_CI: Task.FIX_CI is still at a"))

    def test_a_task_the_table_lacks_is_refused(self) -> None:
        """No entry, no effects to do."""
        found = said(
            "HAND_BACK",
            Seed(
                path="workerselect.py",
                old="        _of(Task.HAND_BACK, BACK, BACK),\n",
                new="",
            ),
        )
        assert_that(found, contains_string("has no entry in the table"))

    def test_an_empty_package_is_refused(self) -> None:
        """Nothing to read the effects from."""
        found = witnessproofs.progress_of("FIX_CI", proofseeds.shipped_step)(
            proofsource.of_texts({})
        )
        assert_that(found, has_length(1))

    def test_each_proof_holds_and_finds_its_seed(self) -> None:
        """What ``proofseeds`` requires of the proofs of the package."""
        for bullet, case in CASES.items():
            with self.subTest(bullet=bullet):
                whole = proofsource.of_texts(package_texts())
                seeded = proofsource.of_texts(
                    proofseeds.seeded(package_texts(), case.seed)
                )
                assert_that(case.proof(whole), equal_to([]))
                assert_that(case.proof(seeded)[0], starts_with(f"{bullet}:"))

    def test_each_task_has_a_seed(self) -> None:
        """One proof for each task, each with its seed."""
        assert_that(
            set(CASES),
            equal_to({f"P13.4.{t.name}" for t in workerselect.Task}),
        )

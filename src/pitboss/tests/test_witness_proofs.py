"""P13.4: after its entry's required effects, a task's PR is not at a worker.

pitboss#526 (keyword: progress, witnesses). For each ``Task`` there is a PR the
shipped decider gives the task (``witnesses``). The proof takes the effects the
task's entry of ``workerselect.TABLE`` requires, read from the source it was given,
does them to that PR as the shipped command writes them, and runs the decider again:
a step that is the same, or any worker's, is a finding. The decider is run, never
copied, so an entry that requires an effect the step is not decided from (a hand-back
for a red check) is refused by this proof alone: it has the shape P13.3 asks for.

A seed for each task makes its entry require nothing; the proofs of the other tasks
still hold. The proofs are in this test module, not in ``onepathproofs``: they run the
witnesses, which are the tests' states, and a proof of the package that imports the
tests is a cycle of the package with them. The tests of this module require each to
hold on the package and to find its seed, as ``proofseeds`` does for the others.
"""

import functools
import pathlib
import unittest
from typing import Mapping

from hamcrest import assert_that, contains_string, equal_to, has_length, starts_with

from .. import proofseeds, proofsource, selectorproofs, workerselect
from ..proofcase import Case, Proof, Seed
from ..proofsource import Package
from . import witnesses


def progress_of(task: str) -> Proof:
    """The proof that one task's required effects move its PR on.

    Args:
        task: the name of the task.

    Returns:
        P13.4 for the task: a finding when, after the effects its entry of the table
        in the source requires, the decider's step is the task's or another worker's.
    """

    def proof(package: Package) -> list[str]:
        required = selectorproofs.required_in(package)
        if task not in required:
            return [f"P13.4.{task}: Task.{task} has no entry in the table"]
        names = sorted(required[task])
        effects = frozenset(workerselect.Effect[each] for each in names)
        again = witnesses.of(workerselect.Task[task], effects)
        said = f"P13.4.{task}: Task.{task} is still at a worker after {names}"
        return [said] if witnesses.stuck(again) else []

    return proof


def _seed(task: workerselect.Task) -> Seed:
    # a last entry of the task that requires nothing replaces the table's own
    return Seed(
        path="workerselect.py",
        old="",
        new=f"_of(Task.{task.name}, frozenset(), frozenset())",
    )


CASES: Mapping[str, Case] = {
    f"P13.4.{task.name}": Case(proof=progress_of(task.name), seed=_seed(task))
    for task in workerselect.Task
}


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
    return "\n".join(progress_of(task)(package))


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
        found = progress_of("FIX_CI")(proofsource.of_texts({}))
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

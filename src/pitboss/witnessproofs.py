"""P13.4: after its entry's required effects, a task's PR is not at a worker.

pitboss#526 (keyword: progress, witnesses). For each ``Task`` there is a PR the
shipped decider gives the task (``witnesses``, made of ``witnessstates``). The proof
takes the effects the task's entry of ``workerselect.TABLE`` requires, read from the
source it was given, does them to that PR as the shipped command writes them, and
runs the decider again: a step that is the same, or any worker's, is a finding. The
decider is run, never copied, so an entry that requires an effect the step is not
decided from (a hand-back for a red check) is refused by this proof alone: it has
the shape P13.3 asks for. A seed for each task makes its entry require nothing; the
proofs of the other tasks still hold.
"""

from typing import Mapping

from . import selectorproofs, witnesses, workerselect
from .proofcase import Case, Proof, Seed
from .proofsource import Package


def progress_of(task: str, decided: witnesses.Decider) -> Proof:
    """The proof that one task's required effects move its PR on.

    Args:
        task: the name of the task.
        decided: the shipped decider (``proofseeds`` gives it: a proof of the
            package imports nothing the decider imports, the depth of the package).

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
        return [said] if witnesses.stuck(again, decided) else []

    return proof


def _seed(task: workerselect.Task) -> Seed:
    # a last entry of the task that requires nothing replaces the table's own
    return Seed(
        path="workerselect.py",
        old="",
        new=f"_of(Task.{task.name}, frozenset(), frozenset())",
    )


def cases(decided: witnesses.Decider) -> Mapping[str, Case]:
    """P13.4 for each task, with its seed.

    Args:
        decided: the shipped decider.

    Returns:
        Each proof by its bullet.
    """
    return {
        f"P13.4.{task.name}": Case(
            proof=progress_of(task.name, decided), seed=_seed(task)
        )
        for task in workerselect.Task
    }

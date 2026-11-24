"""The ``act`` verb each step's decision carries out (keyword: accepts).

A leaf of the module graph: ``decide`` makes the decision with it and
``actiongates`` checks that a step that carries a gated verb has a gate.
"""

from typing import Mapping

from . import answer, steps

CARRIED: Mapping[steps.Step, answer.Carried] = {  # the gated verb of each step
    steps.Step.MERGE: answer.Carried.MERGE,
    steps.Step.UNDRAFT: answer.Carried.UNDRAFT,
    steps.Step.REGULAR_REVIEW: answer.Carried.REVIEW,
    steps.Step.WORKER: answer.Carried.PUSH,
    steps.Step.RUN_E2E: answer.Carried.DISPATCH,
}

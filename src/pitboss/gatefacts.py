"""What a PR at the merge or the undraft step is gated on (keyword: gate).

A record of the world (``world.PullRecord.gated``), read by ``gateread`` and decided
by ``gate``.
"""

import dataclasses
from typing import Mapping

from . import pullrecords, steps
from .totaljson import JsonMap

# the act each gated step takes
ACTIONS: Mapping[steps.Step, str] = {
    steps.Step.MERGE: "arm",
    steps.Step.UNDRAFT: "undraft",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Gate:
    """What a PR at the merge or the undraft step is gated on, as GitHub answered.

    Attributes:
        pull: the PR object.
        inputs: the other inputs (the head's runs, the files, the tickets, the
            timeline, the holds, the blockers, the rules).
        state: the same, typed once (plan 6.1); the rows move to it one by one.
    """

    pull: JsonMap
    inputs: JsonMap
    state: pullrecords.GateState

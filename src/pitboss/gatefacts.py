"""What a PR at the merge or the undraft step is gated on (keyword: gate).

A record of the world (``world.PullRecord.gated``), read by ``gateread`` and decided
by ``gate``.
"""

import dataclasses
from typing import Mapping

from . import pullrecords, steps

# the act each gated step takes
ACTIONS: Mapping[steps.Step, str] = {
    steps.Step.MERGE: "arm",
    steps.Step.UNDRAFT: "undraft",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Gate:
    """What a PR at the merge or the undraft step is gated on.

    Attributes:
        state: the PR and the inputs read with it, typed once (plan 6.1).
    """

    state: pullrecords.GateState

"""The gate's stops as a word and lines, as the act tests compare (keyword: gate)."""

from .. import gate, gatefacts, gatepolicy
from ..totaljson import JsonMap
from .gatewords import GO, STOP, Answer, Word

__all__ = ["GO", "STOP", "Answer", "Word", "verdict"]


def verdict(
    action: str, pull: JsonMap, ctx: JsonMap, policy: gatepolicy.Policy | None = None
) -> Answer:
    """The gate's stops of an action on a PR.

    Args:
        action: ``merge``, ``arm`` or ``undraft``.
        pull: the PR.
        ctx: its inputs.
        policy: the readings (as shipped when None).

    Returns:
        GO when nothing stops it; STOP with the lines otherwise.
    """
    found = gate.stops_for(action, gatefacts.Gate(pull=pull, inputs=ctx), policy)
    return Answer(
        word=STOP if found else GO, lines=[each.line for each in found], stops=found
    )

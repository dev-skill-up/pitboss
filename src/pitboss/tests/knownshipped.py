"""The kit the known cases run on, every control as pitboss ships it."""

import functools

from .. import actcore, actverbs, decide, gate, gatepolicy
from . import fakehub
from . import knownkit
from .knownkit import Kit


@functools.cache
def rests() -> fakehub.Given:
    """The gate and the act verbs' controls as pitboss ships them.

    Returns:
        What a fake GitHub's verbs rest on.
    """
    return fakehub.Given(
        controls=actcore.Controls(),
        gating=gate.stops_for,
        deciding=decide.step_decision,
        policy=gatepolicy.shipped(),
    )


def shipped() -> Kit:
    """Every control as pitboss ships it.

    Returns:
        The kit.
    """
    return Kit(rests=rests(), verbs=actverbs.VERBS)


GIVEN = shipped()


def refusal(hub: fakehub.Made, verb: str, **options: str) -> str:
    """Run a verb of the shipped kit on the world's PR and say how it was refused.

    Args:
        hub: the hub and the verb's world.
        verb: the verb.
        **options: its options.

    Returns:
        The refusal's text, or "" when it went.
    """
    return knownkit.refusal(GIVEN, hub, verb, **options)

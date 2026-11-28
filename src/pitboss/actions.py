"""Actions: each checks the item is at one of the steps it acts for, then writes."""

import dataclasses
from collections.abc import Mapping, Set
from typing import Protocol

from . import machine, parse


class Hub(Protocol):
    """The writes: one method, the verb says which."""

    def write(self, ask: "Ask", number: int) -> None:
        """Write one verb on one PR.

        Args:
            ask: the verb and its text.
            number: the PR.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ask:
    """A verb asked for.

    Attributes:
        verb: a key of ``STEPS``.
        text: a comment body or a label name, empty otherwise.
    """

    verb: str
    text: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Done:
    """The action ran.

    Attributes:
        verb: the verb that ran.
    """

    verb: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Refused:
    """The item is not at a step the action is for.

    Attributes:
        wanted: the steps the verb is for.
        found: the step the item is at.
    """

    wanted: Set[machine.Step]
    found: machine.Step


Outcome = Done | Refused

STEPS: Mapping[str, Set[machine.Step]] = {
    "merge": {machine.Step.MERGE},
    "undraft": {machine.Step.UNDRAFT},
    "update-branch": {machine.Step.FIX_CONFLICT},
    "rerun": {machine.Step.FIX_CI},
    "dispatch": {machine.Step.RUN_E2E},
    "close": set(),
    "label": set(),
    "comment": set(),
}


def run(ask: Ask, hub: Hub, pr: parse.Pull, gates: machine.Gates) -> Outcome:
    """Run a verb on a PR when the PR is at a step the verb is for.

    Args:
        ask: the verb and its text; an empty set of steps in ``STEPS`` is any step.
        hub: the writes.
        pr: the PR.
        gates: holds and pressure.

    Returns:
        ``Done``, or ``Refused`` with nothing written.
    """
    found = machine.pull_step(pr, gates)
    wanted = STEPS[ask.verb]
    if wanted and found not in wanted:
        return Refused(wanted=wanted, found=found)
    hub.write(ask, pr.number)
    return Done(verb=ask.verb)

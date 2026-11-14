"""The decisions a fake GitHub's verbs look themselves up in (keyword: act-verbs).

``Decider`` is the one read of an ``act`` command over the fake: the kit's decisions,
the PR's own as ``next`` decides it, and the verb's answer as ``decide`` makes it
(``actdecide.verdict`` of what ``actread`` reads and of the hub's hold issues).
"""

import dataclasses
from typing import MutableSequence

from .. import actdecide, actfacts, actread, answer, gatefacts, holdparse
from .. import pullstate, steps
from ..actcore import Act
from .fakegiven import Given


def held(act: Act) -> holdparse.Held:
    """The hold issues of the act's repositories, as the hub has them.

    Args:
        act: the verb's world.

    Returns:
        Each repository's holds, parsed as the one read parses them.
    """
    return {
        repo: [
            holdparse.parse(each) for each in act.hub.issues(repo, holdparse.HOLD_LABEL)
        ]
        for repo in act.repos
    }


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Decider:
    """A world's decisions as ``next`` and ``decide`` make them, over the hub now.

    Attributes:
        kit: the gate's rows and the decisions of the rest of the world.
        name: the world's PR, ``owner/name#number``.
        acts: the verb's world, once it is made (its one entry): its hub and the
            gate's other inputs.
    """

    kit: Given
    name: str
    acts: MutableSequence[Act]

    def __call__(self, asked: actfacts.Asked) -> answer.Decided:
        """The kit's decisions, its PR's own, and the verb's answer.

        Args:
            asked: the verb asked for.

        Returns:
            The decisions.
        """
        act = self.acts[0]
        name, (repo, number) = self.name, self.name.split("#")
        pull = act.hub.pull(repo, int(number))
        ctx = act.inputs(repo, int(number), pull, [])
        step = steps.undraft() if pull.get("draft") else steps.merge()
        gated = pullstate.gate_of(pull, ctx)
        found = self.kit.gating(gatefacts.ACTIONS[step.step], gated, self.kit.policy)
        decided = self.kit.deciding(name, pull, step, gated if found else None)
        acting = actdecide.verdict(actread.read(act, asked), held(act), self.kit.rows)
        given = dataclasses.replace(self.kit.decided, acting=acting)
        if decided is None:
            return given
        return dataclasses.replace(given, by_item={**given.by_item, name: decided})

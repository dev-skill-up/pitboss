"""What a fake GitHub's verbs rest on (keyword: act-verbs).

``Given`` is the kit's controls, the gate, the decisions of the rest of the world and
how the verb's own decisions are made (``fakedecider.Decider``, given where the kit
is made, so a hub of the fake reads nothing of ``actread``).
"""

import dataclasses
from typing import Callable, MutableSequence, Protocol, Sequence

from .. import actdecide, answer, gatefacts, gatepolicy, steps
from ..actcore import Act, Controls, Decisions
from ..actport import Pull
from ..gatestop import Stop
from . import hubwork

Gating = Callable[[str, gatefacts.Gate, gatepolicy.Policy], Sequence[Stop]]
Deciding = Callable[
    [str, Pull, steps.Next, gatefacts.Gate | None], answer.Decision | None
]


def work(*items: str) -> answer.Decided:
    """The decisions of a world whose order is the items, each a worker's.

    Args:
        *items: the items, first to take first (``q#10`` when none).

    Returns:
        The decisions.
    """
    every = [hubwork.worker(each) for each in items or ["q#10"]]
    return work_of(*every)


def work_of(first: answer.Decision, *rest: answer.Decision) -> answer.Decided:
    """The decisions of a world in the order of the decisions given.

    Args:
        first: the first decision.
        *rest: the others.

    Returns:
        The decisions; no act verb stands.
    """
    return answer.Decided(
        answer=answer.Work(first=first, rest=rest, free=1),
        by_item={each.item: each for each in (first, *rest)},
        acting=None,
    )


class DeciderOf(Protocol):
    """How a verb's decisions are made over a hub (``fakedecider.Decider``)."""

    def __call__(
        self, *, kit: "Given", name: str, acts: MutableSequence[Act]
    ) -> Decisions:
        """The decisions of a world's PR.

        Args:
            kit: the gate and the decisions of the rest of the world.
            name: the world's PR, ``owner/name#number``.
            acts: the verb's world, once it is made (its one entry).

        Returns:
            The decisions, as each verb asks.
        """


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Given:
    """What a fake GitHub's verbs rest on.

    Attributes:
        controls: the readers and the disarm.
        gating: the gate's stops (``gate.stops_for``).
        policy: the gate's readings.
        deciding: the PR's decision, by the one item decider (``knownshipped``).
        decisions_of: how the verb's decisions are made (``fakedecider.Decider``).
        decided: the decisions ``dispatch-next`` takes the head of.
        rows: the rows of an act verb's decision (``actdecide.ROWS``).
    """

    controls: Controls
    gating: Gating
    policy: gatepolicy.Policy
    deciding: Deciding
    decisions_of: DeciderOf
    decided: answer.Decided = dataclasses.field(default_factory=work)
    rows: actdecide.Rows = actdecide.ROWS

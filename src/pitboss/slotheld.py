"""Which slots are held by work the ledger does not record (keyword: slot-held).

A slot is occupied by an agent the ledger records, and by an agent the session
runs that the ledger does not hold. Reviews count toward the cap as workers do;
Opus research and Opus rulings run outside it (pitboss#291). The lines are plain
text, not markers: each one carries its own rule. This module holds the lines
and the facts; the reading of the agents is ``slotholding``.
"""

import dataclasses
from typing import Sequence

RUNNING_FIRST = "running workers and reviewers: never interrupted, never stopped"
LEAD = 1
NOT_LIMITED = 10**9
NOT_COMPUTED = "slots: not computed, --running names the agents the session runs"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Occupancy:
    """What holds the slots beyond the ledger's agents.

    Attributes:
        unrecorded: the live agents that hold no slot.
        free: how many empty slots no agent holds; none while a live agent is
            unrecorded.
        known: whether the agents the session runs were given (``--running``);
            when not, no slot is said to be held or empty (pitboss#94).
    """

    unrecorded: Sequence[str] = ()
    free: int = NOT_LIMITED
    known: bool = True


UNLIMITED = Occupancy()


def unrecorded_line(name: str) -> str:
    """The line of a live agent that holds no slot.

    Args:
        name: the agent.

    Returns:
        The ``UNRECORDED AGENT`` line.
    """
    return (
        f"UNRECORDED AGENT: {name} runs but holds no slot: run slots set SLOT"
        " AGENT TICKET"
    )


def lines(taken: Occupancy) -> Sequence[str]:
    """The lines that say what holds the slots, in place of ``EMPTY SLOT``.

    Args:
        taken: the occupancy.

    Returns:
        An ``UNRECORDED AGENT`` line for each live agent that holds no slot; the
        one line that says the slots are not computed when the running agents
        were not given.
    """
    if not taken.known:
        return [NOT_COMPUTED]
    return [*map(unrecorded_line, taken.unrecorded)]

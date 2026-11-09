"""Which slots are held by work the ledger does not record (keyword: slot-held).

A slot is occupied by an agent the ledger records, by a PR whose next step is a
worker's round (a fix of the review, the Plan and Execution body, a ruling's
steps, a conflict: that agent is resumed, not started, and leaves no mark the
sweep reads), and by an agent the session runs that the ledger does not hold.
Reviews count toward the cap as workers do; Opus research and Opus rulings run
outside it (pitboss#291). The lines are plain text, not markers: each one
carries its own rule. This module holds the lines and the facts; the reading of
the PRs is ``slotholding``.
"""

import dataclasses
from typing import AbstractSet, Sequence

QUEUED = "QUEUED: waits for a free slot; the running agent is never interrupted"
RUNNING_FIRST = "running workers and reviewers: never interrupted, never stopped"
LEAD = 1
NOT_LIMITED = 10**9
NOT_COMPUTED = "slots: not computed, --running names the agents the session runs"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Held:
    """A PR whose next step holds a slot.

    Attributes:
        reference: the PR.
        step: its next step in words.
    """

    reference: str
    step: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Occupancy:
    """What holds the slots beyond the ledger's agents.

    Attributes:
        holding: the PRs whose next step holds a slot.
        unrecorded: the live agents that hold no slot.
        free: how many empty slots no agent or PR holds; none while a live
            agent is unrecorded.
        references: the PRs that hold a slot, none while a live agent holds none
            (it may be the one working on them).
        known: whether the agents the session runs were given (``--running``);
            when not, no slot is said to be held or empty (pitboss#94).
    """

    holding: Sequence[Held] = ()
    unrecorded: Sequence[str] = ()
    free: int = NOT_LIMITED
    references: AbstractSet[str] = frozenset()
    known: bool = True


UNLIMITED = Occupancy()


def waits(taken: Occupancy, reference: str) -> bool:
    """Whether a step waits for a free slot.

    Args:
        taken: the occupancy.
        reference: the PR or ticket the step is for.

    Returns:
        True when no slot is free and the step is not the round of a PR that
        holds one.
    """
    return taken.free == 0 and reference not in taken.references


def held_line(each: Held) -> str:
    """The line of a PR that holds a slot.

    Args:
        each: the PR.

    Returns:
        ``SLOT HELD: <pr> (<step>)``.
    """
    return f"SLOT HELD: {each.reference} ({each.step})"


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
        A ``SLOT HELD`` line for each PR and an ``UNRECORDED AGENT`` line for
        each live agent that holds no slot; the one line that says the slots
        are not computed when the running agents were not given.
    """
    if not taken.known:
        return [NOT_COMPUTED]
    return [
        *map(held_line, taken.holding),
        *map(unrecorded_line, taken.unrecorded),
    ]

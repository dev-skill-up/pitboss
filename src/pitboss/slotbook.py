"""The ledger's slots and how a ticket is spelled, with no I/O (keyword: one-path).

The world a decision is made from holds a ledger, so its types live apart from
the file ``ledger`` reads and writes: the decider reaches no ledger file (P2).
"""

import dataclasses
import re
from typing import Mapping, Sequence

from . import config

_REFERENCE = re.compile(r"^(?:(?P<owner>[\w.-]+)/)?(?P<name>[\w.-]+)?#(?P<number>\d+)$")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Slot:
    """One worker slot.

    Attributes:
        name: the slot's name.
        model: the model its worker runs on.
        agent: the agent in it, or empty.
        task: what the agent works on (an ``owner/name#number``), or empty.
        waiting: the agent waits (on CI, a review or an answer), not runs.
        started: when the agent was put in the slot (ISO time), or empty.
        heard: when the agent last handed back or notified (ISO time), or empty.
        ticket: the ticket the task works on (an ``owner/name#number``), or
            empty.
        kind: the kind of task (one of ``TASK_KINDS``), or empty.
    """

    name: str
    model: str
    agent: str = ""
    task: str = ""
    waiting: bool = False
    started: str = ""
    heard: str = ""
    ticket: str = ""
    kind: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ledger:
    """Every slot, and the models each ticket has failed with.

    Attributes:
        slots: the slots, in order.
        failed: each ticket's failed models.
        config: the path of the configuration that owns the ledger, a key put
            in the file by hand (nothing writes it when the file is made), or
            empty when the file records none.
        deviations: for each ticket, the deviations a review of its worker's
            work listed (keyword: deviations, pitboss#257).
        checkin: when the orchestrator last posted its status (ISO time), or
            empty when none is recorded (keyword: check-in, pitboss#450).
        checkin_first: the first check-in of the timer job now kept (ISO time):
            the job was made at most one interval before it (keyword: check-in,
            pitboss#471).
    """

    slots: Sequence[Slot]
    failed: Mapping[str, Sequence[str]]
    config: str = ""
    deviations: Mapping[str, Sequence[str]] = dataclasses.field(default_factory=dict)
    checkin: str = ""
    checkin_first: str = ""


def reference(text: str, project: config.Repo) -> str:
    """Spell a ticket or PR as ``owner/name#number``.

    Args:
        text: ``#12``, ``name#12`` or ``owner/name#12``.
        project: the repository of a bare ``#12``, and the owner of ``name#12``.

    Returns:
        The full reference, or ``text`` when it is not a reference.
    """
    found = _REFERENCE.match(text.strip())
    if found is None:
        return text
    owner = found.group("owner") or project.owner
    name = found.group("name") or project.name
    return f"{owner}/{name}#{found.group('number')}"

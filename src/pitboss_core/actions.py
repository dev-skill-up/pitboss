"""Actions: each checks the item is in the step it acts for, then acts via a port."""

import dataclasses
from typing import Protocol

from . import machine, parse


class Hub(Protocol):
    """The writes, one method each (the edge; tests pass a fake)."""

    def merge(self, number: int) -> None: ...
    def undraft(self, number: int) -> None: ...
    def comment(self, number: int, body: str) -> None: ...


@dataclasses.dataclass(frozen=True, slots=True)
class Done:
    """The action ran."""

    what: str


@dataclasses.dataclass(frozen=True, slots=True)
class Refused:
    """The item is not in the step the action is for."""

    wanted: machine.Step
    found: machine.Step


def merge(hub: Hub, pr: parse.Pull) -> Done | Refused:
    """Merge a PR that is at MERGE.

    Args:
        hub: the writes.
        pr: the PR.

    Returns:
        The outcome.
    """
    found = machine.pull_step(pr)
    if found is not machine.Step.MERGE:
        return Refused(machine.Step.MERGE, found)
    hub.merge(pr.number)
    return Done("merged")


def undraft(hub: Hub, pr: parse.Pull) -> Done | Refused:
    """Mark ready a PR that is at UNDRAFT.

    Args:
        hub: the writes.
        pr: the PR.

    Returns:
        The outcome.
    """
    found = machine.pull_step(pr)
    if found is not machine.Step.UNDRAFT:
        return Refused(machine.Step.UNDRAFT, found)
    hub.undraft(pr.number)
    return Done("undrafted")

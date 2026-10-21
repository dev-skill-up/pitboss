"""The worker-slot ledger: which slot runs which agent on which task."""

import dataclasses
import json
import pathlib
import re
from typing import Iterable, Mapping, Sequence

from . import config

_REFERENCE = re.compile(r"^(?:(?P<owner>[\w.-]+)/)?(?P<name>[\w.-]+)?#(?P<number>\d+)$")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Refusal:
    """A change the ledger refuses.

    Attributes:
        reason: why, and what to do instead.
    """

    reason: str


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Slot:
    """One worker slot.

    Attributes:
        name: the slot's name.
        model: the model its worker runs on.
        agent: the agent in it, or empty.
        task: what the agent works on (an ``owner/name#number``), or empty.
    """

    name: str
    model: str
    agent: str = ""
    task: str = ""


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ledger:
    """Every slot, and the models each ticket has failed with.

    Attributes:
        slots: the slots, in order.
        failed: each ticket's failed models.
    """

    slots: Sequence[Slot]
    failed: Mapping[str, Sequence[str]]


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


def read(path: pathlib.Path, defaults: Iterable[config.SlotSpec]) -> Ledger:
    """Read the ledger, or start one from the configured slots.

    Args:
        path: the ledger file.
        defaults: the slots a new ledger starts with.

    Returns:
        The ledger.
    """
    if not path.exists():
        return Ledger(
            slots=tuple(Slot(name=spec.name, model=spec.model) for spec in defaults),
            failed={},
        )
    data = json.loads(path.read_text())
    return Ledger(
        slots=tuple(Slot(**item) for item in data["slots"]),
        failed={key: tuple(value) for key, value in data["failed"].items()},
    )


def write(path: pathlib.Path, ledger: Ledger) -> None:
    """Write the ledger.

    Args:
        path: the ledger file.
        ledger: the ledger.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "slots": [dataclasses.asdict(slot) for slot in ledger.slots],
        "failed": {key: list(value) for key, value in sorted(ledger.failed.items())},
    }
    path.write_text(json.dumps(data, indent=2) + "\n")


def find(ledger: Ledger, name: str) -> Slot | Refusal:
    """Find a slot by name.

    Args:
        ledger: the ledger.
        name: the slot's name.

    Returns:
        The slot, or a refusal when there is no such slot.
    """
    for slot in ledger.slots:
        if slot.name == name:
            return slot
    listed = ", ".join(slot.name for slot in ledger.slots) or "none"
    return Refusal(reason=f"no slot {name!r} (slots: {listed})")


def _replace(ledger: Ledger, name: str, slot: Slot | None) -> Ledger:
    kept = [item if item.name != name else slot for item in ledger.slots]
    return dataclasses.replace(ledger, slots=tuple(item for item in kept if item))


def take(ledger: Ledger, slot_name: str, agent: str, task: str) -> Ledger | Refusal:
    """Put an agent in an empty slot.

    Args:
        ledger: the ledger.
        slot_name: the slot.
        agent: the agent's name.
        task: what it works on.

    Returns:
        The new ledger, or a refusal when the slot is taken (free it first).
    """
    slot = find(ledger, slot_name)
    if isinstance(slot, Refusal):
        return slot
    if slot.agent:
        return Refusal(
            reason=f"slot {slot_name} holds {slot.agent} on {slot.task}: free it first"
        )
    return _replace(
        ledger, slot_name, dataclasses.replace(slot, agent=agent, task=task)
    )


def free(ledger: Ledger, slot_name: str) -> Ledger | Refusal:
    """Empty a slot.

    Args:
        ledger: the ledger.
        slot_name: the slot.

    Returns:
        The new ledger, or a refusal when there is no such slot.
    """
    slot = find(ledger, slot_name)
    if isinstance(slot, Refusal):
        return slot
    return _replace(ledger, slot_name, dataclasses.replace(slot, agent="", task=""))


def add(
    ledger: Ledger, spec: config.SlotSpec, models: Sequence[str]
) -> Ledger | Refusal:
    """Add a slot.

    Args:
        ledger: the ledger.
        spec: the slot's name and model.
        models: the configured models.

    Returns:
        The new ledger, or a refusal when the name is taken or the model is
        not configured.
    """
    if any(slot.name == spec.name for slot in ledger.slots):
        return Refusal(reason=f"slot {spec.name} already exists")
    if spec.model not in models:
        configured = ", ".join(models) or "none: set [slots] models"
        return Refusal(reason=f"model {spec.model!r} is not one of {configured}")
    added = Slot(name=spec.name, model=spec.model)
    return dataclasses.replace(ledger, slots=(*ledger.slots, added))


def remove(ledger: Ledger, slot_name: str) -> Ledger | Refusal:
    """Remove an empty slot.

    Args:
        ledger: the ledger.
        slot_name: the slot.

    Returns:
        The new ledger, or a refusal when the slot holds an agent (free it
        first).
    """
    slot = find(ledger, slot_name)
    if isinstance(slot, Refusal):
        return slot
    if slot.agent:
        return Refusal(reason=f"slot {slot_name} holds {slot.agent}: free it first")
    return _replace(ledger, slot_name, None)


def record_failure(ledger: Ledger, ticket: str, model: str) -> Ledger:
    """Record that a model failed a ticket, so it goes to a larger one.

    Args:
        ledger: the ledger.
        ticket: the ticket's full reference.
        model: the model that failed.

    Returns:
        The new ledger.
    """
    failed = dict(ledger.failed)
    failed[ticket] = tuple(sorted({*failed.get(ticket, ()), model}))
    return dataclasses.replace(ledger, failed=failed)


def gone(ledger: Ledger, running: Iterable[str]) -> Sequence[Slot]:
    """The slots whose agent the session no longer runs.

    Args:
        ledger: the ledger.
        running: the names of the agents the session runs.

    Returns:
        The slots to free.
    """
    alive = frozenset(running)
    return [slot for slot in ledger.slots if slot.agent and slot.agent not in alive]

"""The worker-slot ledger: which slot runs which agent on which task."""

import dataclasses
import enum
import json
import pathlib
import re
from typing import Callable, Iterable, Mapping, Sequence

from . import config

_REFERENCE = re.compile(r"^(?:(?P<owner>[\w.-]+)/)?(?P<name>[\w.-]+)?#(?P<number>\d+)$")


class Mark(enum.Enum):
    """A time the ledger keeps for an agent.

    Attributes:
        STARTED: when the agent was put in its slot.
        HEARD: when it last handed back or notified.
    """

    STARTED = enum.auto()
    HEARD = enum.auto()


# What a task is: start a PR for a ticket, review a PR, a fix round on a PR (it
# may resume the agent that works on it), or a ruling on a ticket or PR.
TASK_KINDS = ("start", "review", "fix", "ruling")
FIX_ROUND = "fix"


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
        checkin_since: when the check-in timer began its run of check-ins on time
            (ISO time), which its expiry counts from (keyword: check-in,
            pitboss#471).
    """

    slots: Sequence[Slot]
    failed: Mapping[str, Sequence[str]]
    config: str = ""
    deviations: Mapping[str, Sequence[str]] = dataclasses.field(default_factory=dict)
    checkin: str = ""
    checkin_since: str = ""


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
        config=data.get("config", ""),
        deviations={
            key: tuple(value) for key, value in data.get("deviations", {}).items()
        },
        checkin=data.get("checkin", ""),
        checkin_since=data.get("checkin_since", ""),
    )


def configured(settings: config.Config) -> Ledger:
    """Read the configured ledger.

    Args:
        settings: the configuration.

    Returns:
        The ledger.
    """
    return read(settings.slots.ledger, settings.slots.default)


def recorded_config(path: pathlib.Path) -> str:
    """Read only the configuration path a ledger file records.

    Args:
        path: the ledger file.

    Returns:
        The path the file records, or empty when it records none.
    """
    return str(json.loads(path.read_text()).get("config", ""))


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
    if ledger.config:
        data["config"] = ledger.config
    if ledger.deviations:
        data["deviations"] = {
            key: list(value) for key, value in sorted(ledger.deviations.items())
        }
    if ledger.checkin:
        data["checkin"] = ledger.checkin
    if ledger.checkin_since:
        data["checkin_since"] = ledger.checkin_since
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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Work:
    """What an agent is put to.

    Attributes:
        agent: the agent's name.
        task: what it works on (an ``owner/name#number``).
        ticket: the ticket the task works on.
        kind: the kind of task (one of ``TASK_KINDS``).
    """

    agent: str
    task: str
    ticket: str = ""
    kind: str = ""


def take(ledger: Ledger, slot_name: str, work: Work) -> Ledger | Refusal:
    """Put an agent in an empty slot, or a fix round on the agent it holds.

    Args:
        ledger: the ledger.
        slot_name: the slot.
        work: the agent and its task.

    Returns:
        The new ledger, or a refusal when the slot holds another agent, or the
        same agent for a task that is not a fix round (free it first).
    """
    slot = find(ledger, slot_name)
    if isinstance(slot, Refusal):
        return slot
    resumes = slot.agent == work.agent and work.kind == FIX_ROUND
    if slot.agent and not resumes:
        return Refusal(
            reason=f"slot {slot_name} holds {slot.agent} on {slot.task}: free it first"
        )
    taken = Slot(name=slot.name, model=slot.model, **dataclasses.asdict(work))
    return _replace(ledger, slot_name, taken)


def free(ledger: Ledger, slot_name: str, done: str) -> Ledger | Refusal:
    """Empty a slot whose agent has handed back.

    Args:
        ledger: the ledger.
        slot_name: the slot.
        done: the agent that handed back.

    Returns:
        The new ledger, or a refusal when there is no such slot or the slot
        holds another agent than ``done`` (pitboss#227).
    """
    slot = find(ledger, slot_name)
    if isinstance(slot, Refusal):
        return slot
    if slot.agent != done:
        held = slot.agent or "no agent"
        return Refusal(
            reason=f"slot {slot_name} holds {held}, not {done}: only the agent"
            " that handed back is done"
        )
    return _replace(ledger, slot_name, Slot(name=slot.name, model=slot.model))


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


def _with_agent(
    ledger: Ledger, slot_name: str, change: Callable[[Slot], Slot]
) -> Ledger | Refusal:
    slot = find(ledger, slot_name)
    if isinstance(slot, Refusal):
        return slot
    if not slot.agent:
        return Refusal(reason=f"slot {slot_name} is empty: set an agent first")
    return _replace(ledger, slot_name, change(slot))


def wait(ledger: Ledger, slot_name: str, waiting: bool) -> Ledger | Refusal:
    """Say that a slot's agent waits, or runs again.

    Args:
        ledger: the ledger.
        slot_name: the slot.
        waiting: True when the agent waits, False when it runs.

    Returns:
        The new ledger, or a refusal when the slot has no agent.
    """
    return _with_agent(
        ledger, slot_name, lambda slot: dataclasses.replace(slot, waiting=waiting)
    )


def stamp(ledger: Ledger, slot_name: str, mark: Mark, when: str) -> Ledger | Refusal:
    """Say when a slot's agent started, or last handed back or notified.

    Args:
        ledger: the ledger.
        slot_name: the slot.
        mark: which time.
        when: the time (ISO).

    Returns:
        The new ledger, or a refusal when the slot has no agent.
    """

    def change(slot: Slot) -> Slot:
        if mark is Mark.STARTED:
            return dataclasses.replace(slot, started=when)
        return dataclasses.replace(slot, heard=when)

    return _with_agent(ledger, slot_name, change)

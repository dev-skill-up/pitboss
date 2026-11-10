"""``slots watch``: the ledger kept from the agents' transcripts (slots-watch).

Hooks do not run in a cloud session (Claude Code's "Settings in cloud sessions"),
so a long-running command for the Monitor tool writes the ledger itself
(pitboss#415): a transcript it has not seen becomes a row, a finished agent's row
is freed, a dead one (written before the process started) is freed too.
"""

import dataclasses
import datetime
from typing import Mapping, Sequence

from . import agenttranscript, ledger, slotsheader
from .agenttranscript import State
from .markers import Marker


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Step:
    """What one reading of the transcripts did to the ledger.

    Attributes:
        book: the ledger after it.
        lines: the lines to print: a ``LEDGER CHANGED`` line for each change,
            an ``OVERCAP`` line for each live agent with no free slot.
        changed: the ledger differs from the one given.
        began: the slots a row was put in.
    """

    book: ledger.Ledger
    lines: Sequence[str]
    changed: bool
    began: Sequence[str] = ()


def _reason(
    slot: ledger.Slot,
    states: Mapping[str, State],
    started: datetime.datetime | None,
) -> str:
    # why a row is freed, or empty when it stays
    if not slot.agent:
        return ""
    state = states.get(slot.agent)
    if state in agenttranscript.LEAVING:
        return agenttranscript.WORDS[state]
    began = datetime.datetime.fromisoformat(slot.started) if slot.started else None
    if state is None and started and began and began < started:
        return "no transcript"
    return ""


def _freed(
    book: ledger.Ledger,
    agents: Sequence[agenttranscript.Agent],
    started: datetime.datetime | None,
) -> tuple[ledger.Ledger, Sequence[str]]:
    states = {each.name: each.state for each in agents}
    why = {slot.name: _reason(slot, states, started) for slot in book.slots}
    lines = [
        f"{Marker.LEDGER_CHANGED.text}: slot {slot.name} freed from {slot.agent}"
        f" ({slot.ticket or slot.task}): {why[slot.name]}"
        for slot in book.slots
        if why[slot.name]
    ]
    slots = tuple(
        ledger.Slot(name=slot.name, model=slot.model) if why[slot.name] else slot
        for slot in book.slots
    )
    return dataclasses.replace(book, slots=slots), lines


def _taken(
    book: ledger.Ledger, agents: Sequence[agenttranscript.Agent], now: datetime.datetime
) -> tuple[ledger.Ledger, Sequence[str], Sequence[str]]:
    seen = {slot.agent for slot in book.slots}
    lines: list[str] = []
    began: list[str] = []
    for each in agents:
        empty = next((slot for slot in book.slots if not slot.agent), None)
        if each.state is not State.RUNNING or each.name in seen:
            continue
        if empty is None:
            lines.append(f"OVERCAP {each.name} {each.task or 'no ticket'}")
            continue
        work = ledger.Work(
            agent=each.name, task=each.task, ticket=each.task, kind=each.kind
        )
        taken = ledger.take(book, empty.name, work)
        assert isinstance(taken, ledger.Ledger)  # the slot is empty
        stamped = ledger.stamp(taken, empty.name, ledger.Mark.STARTED, now.isoformat())
        assert isinstance(stamped, ledger.Ledger)  # the slot has its agent
        book = stamped
        began.append(empty.name)
        lines.append(
            f"{Marker.LEDGER_CHANGED.text}: slot {empty.name} takes {each.name}"
            f" on {each.task or 'no ticket'}"
        )
    return book, lines, began


def step(
    book: ledger.Ledger,
    agents: Sequence[agenttranscript.Agent],
    now: datetime.datetime,
    started: datetime.datetime | None,
) -> Step:
    """Bring the ledger up to the transcripts.

    Args:
        book: the ledger.
        agents: the session's agents.
        now: the time now.
        started: when the Claude process of the session started, or None.

    Returns:
        The new ledger and the lines.
    """
    freed, said = _freed(book, agents, started)
    taken, took, began = _taken(freed, agents, now)
    return Step(book=taken, lines=[*said, *took], changed=taken != book, began=began)


def running(book: ledger.Ledger) -> Sequence[str]:
    """The names of the agents a ledger holds.

    Args:
        book: the ledger.

    Returns:
        The agent of each row that has one.
    """
    return [slot.agent for slot in slotsheader.running(book)]

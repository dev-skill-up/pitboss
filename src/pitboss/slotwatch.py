"""``slots watch``: the ledger kept from the agents' transcripts (slots-watch).

Hooks do not run in a cloud session (Claude Code's "Settings in cloud sessions"),
so a long-running command for the Monitor tool writes the ledger itself
(pitboss#415): a transcript it has not seen becomes a row, a finished agent's row
is freed, and so is a dead one (written before the process started).
"""

import dataclasses
import datetime
from typing import Mapping, Sequence

from . import agenttranscript, ledger, slotsheader
from .agenttranscript import State
from .markers import Marker


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Reading:
    """What one reading of the transcripts did to the ledger.

    Attributes:
        book: the ledger after it.
        said: a ``LEDGER CHANGED`` line for each change and an ``OVERCAP`` line
            for each live agent with no free slot.
        changed: the ledger differs from the one given.
    """

    book: ledger.Ledger
    said: Sequence[str]
    changed: bool


def _reason(
    slot: ledger.Slot,
    seen: Mapping[str, State],
    started: datetime.datetime | None,
) -> str:
    # why a row is freed, or empty when it stays
    if not slot.agent:
        return ""
    mine = seen.get(slot.agent)
    if mine in agenttranscript.LEAVING:
        return agenttranscript.WORDS[mine]
    began = datetime.datetime.fromisoformat(slot.started) if slot.started else None
    if mine is None and started and began and began < started:
        return "no transcript"
    return ""


def _release(book: ledger.Ledger, slot: ledger.Slot) -> ledger.Ledger:
    freed = ledger.free(book, slot.name, slot.agent)
    assert isinstance(freed, ledger.Ledger)  # the slot holds that agent
    return freed


def _freed(
    book: ledger.Ledger,
    agents: Sequence[agenttranscript.Agent],
    started: datetime.datetime | None,
) -> tuple[ledger.Ledger, Sequence[str]]:
    seen = {each.name: each.state for each in agents}
    why = {slot.name: _reason(slot, seen, started) for slot in book.slots}
    said = [
        f"{Marker.LEDGER_CHANGED.text}: slot {slot.name} freed from {slot.agent}"
        f" ({slot.ticket or slot.task}): {why[slot.name]}"
        for slot in book.slots
        if why[slot.name]
    ]
    for slot in book.slots:
        if why[slot.name]:
            book = _release(book, slot)
    return book, said


def _put(
    book: ledger.Ledger, slot: str, each: agenttranscript.Agent, now: datetime.datetime
) -> ledger.Ledger:
    work = ledger.Work(
        agent=each.name, task=each.task, ticket=each.task, kind=each.kind
    )
    taken = ledger.take(book, slot, work)
    assert isinstance(taken, ledger.Ledger)  # the slot is empty
    stamped = ledger.stamp(taken, slot, ledger.Mark.STARTED, now.isoformat())
    assert isinstance(stamped, ledger.Ledger)  # the slot has its agent
    return stamped


def _taken(
    book: ledger.Ledger, agents: Sequence[agenttranscript.Agent], now: datetime.datetime
) -> tuple[ledger.Ledger, Sequence[str]]:
    held = {slot.agent for slot in book.slots}
    said: list[str] = []
    for each in agents:
        empty = next((slot.name for slot in book.slots if not slot.agent), None)
        if each.state is not State.RUNNING or each.name in held:
            continue
        task = each.task or "no ticket"
        if empty is None:
            said.append(f"OVERCAP {each.name} {task}")
            continue
        book = _put(book, empty, each, now)
        said.append(
            f"{Marker.LEDGER_CHANGED.text}: slot {empty} takes {each.name} on {task}"
        )
    return book, said


def read(
    book: ledger.Ledger,
    agents: Sequence[agenttranscript.Agent],
    now: datetime.datetime,
    started: datetime.datetime | None,
) -> Reading:
    """Bring the ledger up to the transcripts.

    Args:
        book: the ledger.
        agents: the session's agents.
        now: the time now.
        started: when the Claude process of the session started, or None.

    Returns:
        The new ledger and the lines.
    """
    freed, gone = _freed(book, agents, started)
    after, came = _taken(freed, agents, now)
    return Reading(book=after, said=[*gone, *came], changed=after != book)


def running(book: ledger.Ledger) -> Sequence[str]:
    """The names of the agents a ledger holds.

    Args:
        book: the ledger.

    Returns:
        The agent of each row that has one.
    """
    return [slot.agent for slot in slotsheader.running(book)]

"""The slot log: every change of a slot's state, and the time spent in each."""

import dataclasses
import datetime
import enum
import json
import pathlib
from typing import Mapping, Sequence

from . import ledger


class State(enum.Enum):
    """What a slot is doing.

    Attributes:
        RUNNING: its agent works.
        WAITING: its agent waits (on CI, a review or an answer).
        EMPTY: it has no agent.
        REMOVED: the slot is gone; no slot time passes.
    """

    RUNNING = enum.auto()
    WAITING = enum.auto()
    EMPTY = enum.auto()
    REMOVED = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Entry:
    """One line of the log: a slot entered a state.

    Attributes:
        time: when, in UTC.
        slot: the slot's name.
        state: the state it entered.
        agent: the agent in it, or empty.
        task: the agent's task, or empty.
    """

    time: datetime.datetime
    slot: str
    state: State
    agent: str
    task: str


def state_of(slot: ledger.Slot) -> State:
    """The state of a slot.

    Args:
        slot: the slot.

    Returns:
        Empty without an agent, else waiting or running.
    """
    if not slot.agent:
        return State.EMPTY
    return State.WAITING if slot.waiting else State.RUNNING


def utc(moment: datetime.datetime) -> datetime.datetime:
    """A time in UTC; a time with no zone is taken to be UTC.

    Args:
        moment: the time.

    Returns:
        The same instant in UTC.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=datetime.timezone.utc)
    return moment.astimezone(datetime.timezone.utc)


def _parse(line: str) -> Entry:
    item = json.loads(line)
    return Entry(
        time=utc(datetime.datetime.fromisoformat(item["time"])),
        slot=item["slot"],
        state=State[item["state"].upper()],
        agent=item["agent"],
        task=item["task"],
    )


def read(path: pathlib.Path) -> Sequence[Entry]:
    """Read the log.

    Args:
        path: the log file.

    Returns:
        Its entries in file order; none when there is no file.
    """
    if not path.exists():
        return ()
    return [_parse(line) for line in path.read_text().splitlines()]


def _line(entry: Entry) -> str:
    return (
        json.dumps(
            {
                "time": utc(entry.time).isoformat(),
                "slot": entry.slot,
                "state": entry.state.name.lower(),
                "agent": entry.agent,
                "task": entry.task,
            }
        )
        + "\n"
    )


def append(path: pathlib.Path, entries: Sequence[Entry]) -> None:
    """Append entries to the log, a line each; the log's directory must exist.

    Args:
        path: the log file.
        entries: the entries.
    """
    with path.open("a") as stream:
        stream.writelines(map(_line, entries))


def _current(slot: ledger.Slot, now: datetime.datetime) -> Entry:
    return Entry(
        time=now, slot=slot.name, state=state_of(slot), agent=slot.agent, task=slot.task
    )


def _gone(name: str, now: datetime.datetime) -> Entry:
    return Entry(time=now, slot=name, state=State.REMOVED, agent="", task="")


def changes(
    logged: Sequence[Entry], book: ledger.Ledger, now: datetime.datetime
) -> Sequence[Entry]:
    """The entries that bring the log up to the ledger.

    A slot the log has never seen is logged in whatever state it is in, so
    time before the first change is counted too.

    Args:
        logged: the log so far.
        book: the ledger.
        now: the time now.

    Returns:
        One entry for each slot whose state, agent or task differs from its
        last entry, and one ``REMOVED`` for each slot the ledger lost.
    """
    latest = {entry.slot: entry for entry in logged}
    current = [_current(slot, now) for slot in book.slots]
    found = [
        entry
        for entry in current
        if entry.slot not in latest or _key(latest[entry.slot]) != _key(entry)
    ]
    kept = {entry.slot for entry in current}
    departed = [
        _gone(slot, now)
        for slot, entry in latest.items()
        if slot not in kept and entry.state is not State.REMOVED
    ]
    return [*found, *departed]


def _key(entry: Entry) -> tuple[State, str, str]:
    return entry.state, entry.agent, entry.task


def seconds(
    entries: Sequence[Entry], since: datetime.datetime, until: datetime.datetime
) -> Mapping[str, Mapping[State, float]]:
    """Replay the log: the seconds each slot spent in each state in a window.

    Args:
        entries: the log.
        since: the window's start.
        until: the window's end.

    Returns:
        For each slot with time in the window, its seconds in each state; a
        removed slot has none.
    """
    ordered = sorted(entries, key=lambda entry: entry.time)
    found: dict[str, dict[State, float]] = {}
    for index, entry in enumerate(ordered):
        following = [item for item in ordered[index + 1 :] if item.slot == entry.slot]
        end = min(following[0].time if following else until, until)
        start = max(entry.time, since)
        if entry.state is not State.REMOVED and end > start:
            spent = found.setdefault(entry.slot, {}).setdefault(entry.state, 0.0)
            found[entry.slot][entry.state] = spent + (end - start).total_seconds()
    return found


STATES = (State.RUNNING, State.WAITING, State.EMPTY)


def _shares(spent: Mapping[State, float]) -> str:
    total = sum(spent.values())
    parts = [
        f"{state.name.lower()} {100 * spent.get(state, 0.0) / total:.1f}%"
        for state in STATES
    ]
    return f"{', '.join(parts)} of {total:.0f} s"


def lines(
    entries: Sequence[Entry], since: datetime.datetime, until: datetime.datetime
) -> Sequence[str]:
    """The report: the share of slot time in each state, for each slot and all.

    Args:
        entries: the log.
        since: the window's start.
        until: the window's end.

    Returns:
        The lines.
    """
    spent = seconds(entries, since, until)
    window = f"{since.isoformat()} to {until.isoformat()}"
    if not spent:
        return [f"slot time {window}: none"]
    every = {
        state: sum(per.get(state, 0.0) for per in spent.values()) for state in STATES
    }
    return [
        f"slot time {window}",
        *(f"slot {name}: {_shares(spent[name])}" for name in sorted(spent)),
        f"all slots: {_shares(every)}",
    ]

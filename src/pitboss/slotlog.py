"""The slot log: every change of a slot's state, task, ticket or kind.

It also gives the time spent in each state and on each ticket.
"""

import dataclasses
import datetime
import enum
import json
import pathlib
import statistics
from typing import AbstractSet, Mapping, Sequence

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
        ticket: the ticket the task works on, or empty.
        kind: the kind of task, or empty.
        begun: the entry is a task set (``slots set``), not a wait or resume.
    """

    time: datetime.datetime
    slot: str
    state: State
    agent: str
    task: str
    ticket: str = ""
    kind: str = ""
    begun: bool = False


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
        ticket=item.get("ticket", ""),
        kind=item.get("kind", ""),
        begun=item.get("begun", False),
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
                "ticket": entry.ticket,
                "kind": entry.kind,
                "begun": entry.begun,
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


def _current(slot: ledger.Slot, now: datetime.datetime, begun: str) -> Entry:
    return Entry(
        time=now,
        slot=slot.name,
        state=state_of(slot),
        agent=slot.agent,
        task=slot.task,
        ticket=slot.ticket,
        kind=slot.kind,
        begun=slot.name == begun,
    )


def _gone(name: str, now: datetime.datetime) -> Entry:
    return Entry(time=now, slot=name, state=State.REMOVED, agent="", task="")


def changes(
    logged: Sequence[Entry],
    book: ledger.Ledger,
    now: datetime.datetime,
    begun: str = "",
) -> Sequence[Entry]:
    """The entries that bring the log up to the ledger.

    A slot the log has never seen is logged in whatever state it is in, so
    time before the first change is counted too.

    Args:
        logged: the log so far.
        book: the ledger.
        now: the time now.
        begun: the slot a task was just set in (``slots set``), whose entry is
            logged even when it equals its last one (a fix round that resumes
            the agent), or empty.

    Returns:
        One entry for each slot whose state, agent, task, ticket or kind
        differs from its last entry, and one ``REMOVED`` for each slot the
        ledger lost.
    """
    latest = {entry.slot: entry for entry in logged}
    current = [_current(slot, now, begun) for slot in book.slots]
    found = [entry for entry in current if _differs(latest, entry)]
    kept = {entry.slot for entry in current}
    return [*found, *_departed(latest, kept, now)]


def _departed(
    latest: Mapping[str, Entry], kept: AbstractSet[str], now: datetime.datetime
) -> Sequence[Entry]:
    return [
        _gone(slot, now)
        for slot, entry in latest.items()
        if slot not in kept and entry.state is not State.REMOVED
    ]


def _differs(latest: Mapping[str, Entry], entry: Entry) -> bool:
    last = latest.get(entry.slot)
    return entry.begun or last is None or _key(last) != _key(entry)


def _key(entry: Entry) -> tuple[State, str, str, str, str]:
    return entry.state, entry.agent, entry.task, entry.ticket, entry.kind


def _spans(
    entries: Sequence[Entry], since: datetime.datetime, until: datetime.datetime
) -> Sequence[tuple[Entry, float]]:
    ordered = sorted(entries, key=lambda entry: entry.time)
    found: list[tuple[Entry, float]] = []
    for index, entry in enumerate(ordered):
        following = [item for item in ordered[index + 1 :] if item.slot == entry.slot]
        end = min(following[0].time if following else until, until)
        start = max(entry.time, since)
        if entry.state is not State.REMOVED and end > start:
            found.append((entry, (end - start).total_seconds()))
    return found


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
    found: dict[str, dict[State, float]] = {}
    for entry, spent in _spans(entries, since, until):
        per = found.setdefault(entry.slot, {})
        per[entry.state] = per.get(entry.state, 0.0) + spent
    return found


def ticket_seconds(
    entries: Sequence[Entry], since: datetime.datetime, until: datetime.datetime
) -> Mapping[str, tuple[float, int]]:
    """Replay the log: the worker seconds each ticket took in a window.

    Worker time is the time a slot's agent ran (not waited) on a task of
    the ticket, whatever the task's kind (start, review, fix or ruling).

    Args:
        entries: the log.
        since: the window's start.
        until: the window's end.

    Returns:
        For each ticket with worker time in the window, its seconds and the
        number of task entries (``slots set``) with worker time.
    """
    found: dict[str, tuple[float, int]] = {}
    for entry, spent in _spans(entries, since, until):
        if entry.state is State.RUNNING and entry.ticket:
            total, count = found.get(entry.ticket, (0.0, 0))
            found[entry.ticket] = (total + spent, count + int(entry.begun))
    return found


def ticket_lines(
    entries: Sequence[Entry], since: datetime.datetime, until: datetime.datetime
) -> Sequence[str]:
    """The time report: worker minutes per ticket, with their median and mean.

    Args:
        entries: the log.
        since: the window's start.
        until: the window's end.

    Returns:
        The lines: a header, a line for each ticket with its minutes and the
        count of entries behind them, and the median and mean over tickets.
    """
    spent = ticket_seconds(entries, since, until)
    title = f"worker time per ticket {_window(since, until)}"
    return [title if spent else f"{title}: none", *_ticket_rows(spent)]


def _window(since: datetime.datetime, until: datetime.datetime) -> str:
    return f"{since.isoformat()} to {until.isoformat()}"


def _ticket_rows(spent: Mapping[str, tuple[float, int]]) -> Sequence[str]:
    minutes = {ticket: total / 60 for ticket, (total, _) in spent.items()}
    rows = [
        f"ticket {ticket}: {minutes[ticket]:.1f} min in {spent[ticket][1]} entries"
        for ticket in sorted(spent)
    ]
    if not rows:
        return rows
    median = statistics.median(minutes.values())
    mean = statistics.fmean(minutes.values())
    return [
        *rows,
        f"median {median:.1f} min, mean {mean:.1f} min over {len(rows)} tickets",
    ]


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
    title = f"slot time {_window(since, until)}"
    return [title if spent else f"{title}: none", *_slot_rows(spent)]


def _slot_rows(spent: Mapping[str, Mapping[State, float]]) -> Sequence[str]:
    if not spent:
        return []
    every = {
        state: sum(per.get(state, 0.0) for per in spent.values()) for state in STATES
    }
    return [
        *(f"slot {name}: {_shares(spent[name])}" for name in sorted(spent)),
        f"all slots: {_shares(every)}",
    ]

"""Reading a session's agent transcripts: who they are and what state they are in.

(Keyword: slots-watch, pitboss#415.) A transcript is a ``.output`` file of JSON
lines whose first line has the brief as the user message and the ``agentId``.
Checked on all the transcripts of a session, the last record of a finished agent
is exactly one of: a user record with ``toolEndsTurn`` right after a
``SubagentHandback`` tool_use (workers and reviewers); an assistant record with
the stop reason ``end_turn``; a user record that says ``[Request interrupted by
user`` (stopped or killed). Any other last record is mid-turn: the agent runs, or
it is dead because its file was last written before the Claude process of the
session started. There is no uncertain state, and a slot is never freed on a
guess. The brief mentions the word ``SubagentHandback``, so only the tool_use
``name`` counts.
"""

import dataclasses
import datetime
import enum
import json
import pathlib
import re
from typing import Callable, Iterable, Mapping, Sequence

HANDBACK = "SubagentHandback"
TAIL = 400_000
_MARKER = re.compile(
    r"^PITBOSS-SLOT:\s*(?P<ref>[\w.-]+/[\w.-]+#\d+)"
    r"\s+(?P<kind>start|fix|review|ruling)",
    re.MULTILINE,
)
_GOAL = re.compile(
    r"^Goal:\s*(?P<kind>ticket|review|fix|ruling)\b.*?(?P<ref>[\w.-]+/[\w.-]+#\d+)",
    re.MULTILINE | re.IGNORECASE,
)
KINDS = {"ticket": "start", "review": "review", "fix": "fix", "ruling": "ruling"}


class State(enum.Enum):
    """What a transcript says of its agent.

    Attributes:
        HANDED_BACK: the last record is the result of a ``SubagentHandback``.
        ENDED: the last record is an assistant message that ended its turn.
        STOPPED: the last record is an interruption.
        RUNNING: it is mid-turn, written since the Claude process started.
        DEAD: it is mid-turn, written before the Claude process started.
    """

    HANDED_BACK = enum.auto()
    ENDED = enum.auto()
    STOPPED = enum.auto()
    RUNNING = enum.auto()
    DEAD = enum.auto()


FINISHED = frozenset({State.HANDED_BACK, State.ENDED, State.STOPPED})
LEAVING = FINISHED | {State.DEAD}
WORDS = {
    State.HANDED_BACK: "handback",
    State.ENDED: "handback",
    State.STOPPED: "stopped",
    State.DEAD: "session restarted",
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Agent:
    """One agent of the session.

    Attributes:
        name: its agent id.
        task: the ticket or PR of its brief, or empty.
        kind: the kind of task (``ledger.TASK_KINDS``).
        state: what its transcript says.
        written: when its last record was written.
    """

    name: str
    task: str
    kind: str
    state: State
    written: datetime.datetime


def _message(record: Mapping[str, object]) -> Mapping[str, object]:
    message = record.get("message")
    return message if isinstance(message, dict) else {}


def _content(record: Mapping[str, object]) -> object:
    return _message(record).get("content")


def _blocks(record: Mapping[str, object]) -> Sequence[Mapping[str, object]]:
    content = _content(record)
    return (
        [each for each in content if isinstance(each, dict)]
        if isinstance(content, list)
        else []
    )


def _text(record: Mapping[str, object]) -> str:
    content = _content(record)
    texts = [str(each.get("text", "")) for each in _blocks(record)]
    return content if isinstance(content, str) else "\n".join(texts)


def ending(records: Sequence[Mapping[str, object]]) -> State | None:
    """How the records end, when they end a turn.

    Args:
        records: the tail of the transcript, in order.

    Returns:
        ``HANDED_BACK``, ``ENDED`` or ``STOPPED``; None when the agent is
        mid-turn. An agent that went on after a hand-back it received is
        ``HANDED_BACK`` until a new instruction resumes it (keyword:
        hand-back-done, pitboss#471).
    """
    found = _last_ending(records)
    if found is None and _handed_back_this_turn(records):
        return State.HANDED_BACK
    return found


def _last_ending(records: Sequence[Mapping[str, object]]) -> State | None:
    if not records:
        return None
    last = records[-1]
    stop = _message(last).get("stop_reason")
    if last.get("type") == "assistant":
        asking = any(each.get("type") == "tool_use" for each in _blocks(last))
        return State.ENDED if stop == "end_turn" and not asking else None
    if _text(last).startswith("[Request interrupted by user"):
        return State.STOPPED
    handed = _is_handback_result(records, len(records) - 1)
    return State.HANDED_BACK if handed else None


def _after_handback_call(records: Sequence[Mapping[str, object]], index: int) -> bool:
    # the record before this one calls SubagentHandback
    before = _blocks(records[index - 1]) if index else []
    return any(
        each.get("type") == "tool_use" and each.get("name") == HANDBACK
        for each in before
    )


def _is_handback_result(records: Sequence[Mapping[str, object]], index: int) -> bool:
    # a user record that ends the turn, right after a SubagentHandback call
    return bool(records[index].get("toolEndsTurn")) and _after_handback_call(
        records, index
    )


def _is_new_instruction(record: Mapping[str, object]) -> bool:
    # a user record that is not a tool's result: the brief, or a resumption
    blocks = _blocks(record)
    results = any(each.get("type") == "tool_result" for each in blocks)
    return record.get("type") == "user" and not results


def _handed_back_this_turn(records: Sequence[Mapping[str, object]]) -> bool:
    # keyword: hand-back-done (pitboss#471): a hand-back that was received counts
    # even when the agent went on (it was "waiting on its own background work")
    # until a new instruction resumes it
    for index, each in reversed(list(enumerate(records))):
        if _is_new_instruction(each):
            return False
        if _is_handback_result(records, index):
            return True
    return False


def _task(brief: str) -> tuple[str, str]:
    marked = _MARKER.search(brief)
    if marked:
        return marked.group("ref"), marked.group("kind")
    goal = _GOAL.search(brief)
    if goal:
        return goal.group("ref"), KINDS[goal.group("kind").lower()]
    return "", "start"


def _tail(path: pathlib.Path) -> Sequence[Mapping[str, object]]:
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - TAIL))
        data = stream.read().decode("utf-8", "replace")
    lines = data.splitlines()[1 if size > TAIL else 0 :]
    found = []
    for text in lines:
        try:
            found.append(json.loads(text))
        except ValueError:
            continue
    return [each for each in found if isinstance(each, dict)]


def _head(path: pathlib.Path) -> Mapping[str, object] | None:
    # the first record, when the file is an agent's transcript
    with path.open("rb") as stream:
        first = stream.readline().decode("utf-8", "replace")
    try:
        found = json.loads(first)
    except ValueError:
        return None
    return found if isinstance(found, dict) and "agentId" in found else None


def _written(
    records: Sequence[Mapping[str, object]], head: Mapping[str, object]
) -> datetime.datetime:
    stamps = [str(each["timestamp"]) for each in records if each.get("timestamp")]
    return datetime.datetime.fromisoformat(
        stamps[-1] if stamps else str(head["timestamp"])
    )


def read(path: pathlib.Path, started: datetime.datetime | None) -> Agent | None:
    """Read one transcript.

    Args:
        path: the ``.output`` file.
        started: when the Claude process of the session started, or None when
            it is not known (then no mid-turn agent is dead).

    Returns:
        The agent, or None when the file is not an agent transcript.
    """
    try:
        head = _head(path)
        records = _tail(path) if head is not None else []
    except FileNotFoundError:
        return None  # listed and gone (or a dangling link): normal in a tasks directory
    if head is None:
        return None
    last = _written(records, head)
    task, kind = _task(_text(head))
    state = ending(records)
    if state is None:
        gone = started is not None and last < started
        state = State.DEAD if gone else State.RUNNING
    return Agent(
        name=str(head["agentId"]), task=task, kind=kind, state=state, written=last
    )


Lister = Callable[[pathlib.Path], Iterable[pathlib.Path]]


def agent_files(directory: pathlib.Path) -> Sequence[pathlib.Path]:
    """List the files whose names are an agent's: ``a`` and the id.

    A tasks directory also holds the output of background commands and monitors
    (names that start with ``b``, pitboss#441).

    Args:
        directory: the session's ``tasks`` directory.

    Returns:
        The paths, by file name.
    """
    return sorted(directory.glob("a*.output"))


def read_all(
    directory: pathlib.Path,
    started: datetime.datetime | None,
    lister: Lister = agent_files,
) -> Sequence[Agent]:
    """Read the agent transcripts of a directory.

    Args:
        directory: the session's ``tasks`` directory.
        started: when the Claude process of the session started, or None.
        lister: lists the files to read (a file may be gone when it is read).

    Returns:
        The agents, by file name.
    """
    files = lister(directory)
    return [agent for each in files if (agent := read(each, started))]

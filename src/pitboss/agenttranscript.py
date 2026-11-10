"""Reading a session's agent transcripts: who they are and whether they finished.

(Keyword: slots-watch, pitboss#415.) A transcript is a ``.output`` file of JSON
lines whose first line has the brief as the user message and the ``agentId``.
Facts checked on the session's transcripts:

* a worker that handed back has, after its last assistant record, a tool_use
  named ``SubagentHandback`` and then a tool_result with the success text; a
  later record (a resume by ``SendMessage``) means it runs again;
* a reviewer has no such tool and ends on an assistant message with the stop
  reason ``end_turn`` and no tool_use;
* anything else is running, or silent: an agent with no new line for the idle
  minutes and no hand-back is ``UNCERTAIN`` and is never freed.
"""

import dataclasses
import datetime
import enum
import json
import pathlib
import re
from typing import Mapping, Sequence

HANDBACK = "SubagentHandback"
TAIL = 400_000
_MARKER = re.compile(
    r"^PITBOSS-SLOT:\s*(?P<ref>[\w.-]+/[\w.-]+#\d+)\s+(?P<kind>start|fix|review|ruling)",
    re.MULTILINE,
)
_GOAL = re.compile(
    r"^Goal:\s*(?P<kind>ticket|review|fix|ruling)\b.*?(?P<ref>[\w.-]+/[\w.-]+#\d+)",
    re.MULTILINE | re.IGNORECASE,
)
_REFERENCE = re.compile(r"[\w.-]+/[\w.-]+#\d+")
KINDS = {"ticket": "start", "review": "review", "fix": "fix", "ruling": "ruling"}


class State(enum.Enum):
    """What a transcript says of its agent.

    Attributes:
        RUNNING: it wrote a line within the idle minutes.
        FINISHED: it handed back, or ended its turn.
        SILENT: it did not hand back and wrote nothing for the idle minutes.
    """

    RUNNING = enum.auto()
    FINISHED = enum.auto()
    SILENT = enum.auto()


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Agent:
    """One agent of the session.

    Attributes:
        name: its agent id.
        task: the ticket or PR of its brief, or empty.
        kind: the kind of task (``ledger.TASK_KINDS``).
        state: what its transcript says.
        silent_minutes: minutes since its last line.
    """

    name: str
    task: str
    kind: str
    state: State
    silent_minutes: int


def _blocks(record: Mapping[str, object]) -> Sequence[Mapping[str, object]]:
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return (
        [each for each in content or () if isinstance(each, dict)]
        if (isinstance(content, list))
        else []
    )


def _text(record: Mapping[str, object]) -> str:
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    return "\n".join(str(each.get("text", "")) for each in _blocks(record))


def finished(records: Sequence[Mapping[str, object]]) -> bool:
    """Whether the records end in a hand-back or an ended turn.

    Args:
        records: the tail of the transcript, in order.

    Returns:
        True when the last record is the result of a ``SubagentHandback`` call,
        or an assistant message that ended its turn with no tool call.
    """
    if not records:
        return False
    last = records[-1]
    message = last.get("message")
    stop = message.get("stop_reason") if isinstance(message, dict) else None
    if last.get("type") == "assistant":
        asking = any(each.get("type") == "tool_use" for each in _blocks(last))
        return stop == "end_turn" and not asking
    if len(records) < 2:
        return False
    before = _blocks(records[-2])
    return bool(last.get("toolEndsTurn")) and any(
        each.get("type") == "tool_use" and each.get("name") == HANDBACK
        for each in before
    )


def _task(brief: str) -> tuple[str, str]:
    marked = _MARKER.search(brief)
    if marked:
        return marked.group("ref"), marked.group("kind")
    goal = _GOAL.search(brief)
    if goal:
        return goal.group("ref"), KINDS[goal.group("kind").lower()]
    found = _REFERENCE.search(brief)
    return (found.group(0) if found else ""), "start"


def _tail(path: pathlib.Path) -> Sequence[Mapping[str, object]]:
    with path.open("rb") as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - TAIL))
        data = stream.read().decode("utf-8", "replace")
    lines = data.splitlines()[1 if size > TAIL else 0 :]
    found = []
    for line in lines:
        try:
            found.append(json.loads(line))
        except ValueError:
            continue
    return [each for each in found if isinstance(each, dict)]


def read(path: pathlib.Path, now: datetime.datetime, idle_minutes: int) -> Agent | None:
    """Read one transcript.

    Args:
        path: the ``.output`` file.
        now: the time now.
        idle_minutes: the silence after which an unfinished agent is uncertain.

    Returns:
        The agent, or None when the file is not an agent transcript.
    """
    with path.open("rb") as stream:
        first = stream.readline().decode("utf-8", "replace")
    try:
        head = json.loads(first)
    except ValueError:
        return None
    if not isinstance(head, dict) or "agentId" not in head:
        return None
    records = _tail(path)
    stamps = [str(each["timestamp"]) for each in records if each.get("timestamp")]
    last = datetime.datetime.fromisoformat(stamps[-1] if stamps else head["timestamp"])
    silent = int((now - last).total_seconds() // 60)
    task, kind = _task(_text(head))
    if finished(records):
        state = State.FINISHED
    else:
        state = State.SILENT if silent >= idle_minutes else State.RUNNING
    return Agent(
        name=str(head["agentId"]),
        task=task,
        kind=kind,
        state=state,
        silent_minutes=max(0, silent),
    )


def read_all(
    directory: pathlib.Path, now: datetime.datetime, idle_minutes: int
) -> Sequence[Agent]:
    """Read the agent transcripts of a directory.

    Args:
        directory: the session's ``tasks`` directory.
        now: the time now.
        idle_minutes: the silence after which an unfinished agent is uncertain.

    Returns:
        The agents, by file name.
    """
    found = (
        read(each, now, idle_minutes) for each in sorted(directory.glob("*.output"))
    )
    return [each for each in found if each is not None]

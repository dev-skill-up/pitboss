"""Agent transcripts shaped as the session's ``tasks/*.output`` files (pitboss#415)."""

import json
import pathlib
from typing import Mapping, Sequence

HANDBACK_RESULT = '{"success":true,"message":"Report delivered to your caller."}'


def record(kind: str, when: str, **fields: object) -> Mapping[str, object]:
    """One JSON record of a transcript.

    Args:
        kind: ``user`` or ``assistant``.
        when: its ISO time.
        **fields: the other keys.

    Returns:
        The record.
    """
    return {"type": kind, "timestamp": when, "agentId": "x", **fields}


def brief(agent: str, text: str, when: str) -> Mapping[str, object]:
    """The first record: the brief as the user message.

    Args:
        agent: the agent id.
        text: the brief.
        when: its time.

    Returns:
        The record.
    """
    return record(
        "user", when, agentId=agent, message={"role": "user", "content": text}
    )


def call(name: str, when: str) -> Mapping[str, object]:
    """An assistant record that calls a tool.

    Args:
        name: the tool.
        when: its time.

    Returns:
        The record.
    """
    block = {"type": "tool_use", "id": "t", "name": name, "input": {}}
    message = {"role": "assistant", "stop_reason": "tool_use", "content": [block]}
    return record("assistant", when, message=message)


def result(when: str, text: str = "ok") -> Mapping[str, object]:
    """A user record that carries a tool result.

    Args:
        when: its time.
        text: the result.

    Returns:
        The record.
    """
    block = {"type": "tool_result", "tool_use_id": "t", "content": text}
    return record("user", when, message={"role": "user", "content": [block]})


def turn_end(when: str) -> Mapping[str, object]:
    """The result of a hand-back, which ends the agent's turn.

    Args:
        when: its time.

    Returns:
        The record.
    """
    return {**result(when, HANDBACK_RESULT), "toolEndsTurn": True}


def ended(when: str) -> Mapping[str, object]:
    """An assistant message that ends its turn with no tool call.

    Args:
        when: its time.

    Returns:
        The record.
    """
    message = {
        "role": "assistant",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": "done"}],
    }
    return record("assistant", when, message=message)


def interrupted(when: str) -> Mapping[str, object]:
    """A user record that says the agent was stopped.

    Args:
        when: its time.

    Returns:
        The record.
    """
    block = {"type": "text", "text": "[Request interrupted by user]"}
    return record("user", when, message={"role": "user", "content": [block]})


def write(
    directory: pathlib.Path, agent: str, records: Sequence[Mapping[str, object]]
) -> None:
    """Write a transcript.

    Args:
        directory: the tasks directory.
        agent: the agent id (the file is ``<agent>.output``).
        records: its records.
    """
    directory.mkdir(parents=True, exist_ok=True)
    lines = "".join(json.dumps(each) + "\n" for each in records)
    (directory / f"{agent}.output").write_text(lines)


REAL = pathlib.Path(__file__).parent / "realtranscripts"


def real(agent: str) -> Sequence[Mapping[str, object]]:
    """The records of a real agent's transcript: its brief and its last three.

    The files under ``realtranscripts`` are copied, record for record, from the
    ``tasks/*.output`` files of a real session (the first record and the last
    three).

    Args:
        agent: the agent id.

    Returns:
        The records, as the session wrote them.
    """
    lines = (REAL / f"{agent}.output").read_text().splitlines()
    return [json.loads(each) for each in lines]

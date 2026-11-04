"""A running worker that polls instead of working (keyword: polling, pitboss#175).

A worker that waits for a check by issuing ``Monitor`` calls or ``sleep`` commands
spends a model turn on each. The sweep reads the transcript of each running
worker (the slot's agent name is the ``name`` in the transcript's
``agent-<id>.meta.json``) and prints a ``POLLING`` line for one with over 40 tool
calls whose last 20 are all ``Monitor`` calls or ``sleep`` commands.
"""

import json
import pathlib
from typing import Iterable, Sequence

from . import ledger, toolcalls
from .markers import Marker

MINIMUM_CALLS = 40
LAST_CALLS = 20
# A call of the tool waits when its command holds the text: Monitor always.
NEEDLES = {"Monitor": "", "Bash": "sleep"}


def calls(text: str) -> Sequence[tuple[str, str]]:
    """The tool calls of a transcript, in order.

    Args:
        text: the transcript (JSON lines).

    Returns:
        Each call's tool name and, for a call with a command, the command (else
        empty).
    """
    return [
        (name, str(given.get("command", "")))
        for _, name, given in toolcalls.uses(text.splitlines())
    ]


def waits(call: tuple[str, str]) -> bool:
    """Whether a tool call only waits.

    Args:
        call: the tool name and command.

    Returns:
        True for a ``Monitor`` call or a shell command that sleeps.
    """
    name, command = call
    needle = NEEDLES.get(name)
    return needle is not None and needle in command


def polls(made: Sequence[tuple[str, str]]) -> bool:
    """Whether a worker's calls are a polling loop.

    Args:
        made: its tool calls, in order.

    Returns:
        True when there are over 40 and each of the last 20 only waits.
    """
    return len(made) > MINIMUM_CALLS and all(map(waits, made[-LAST_CALLS:]))


def transcript_of(root: pathlib.Path, agent: str) -> str | None:
    """Read the transcript of the agent with a name.

    Args:
        root: the directory of transcripts, searched recursively.
        agent: the agent's name, as the ledger holds it.

    Returns:
        The text of the transcript whose ``.meta.json`` names the agent, or
        None when there is none.
    """
    for meta in sorted(root.rglob("agent-*.meta.json")):
        try:
            named = json.loads(meta.read_text(encoding="utf-8")).get("name")
        except ValueError:
            continue
        stem = meta.name.removesuffix(".meta.json")
        if named == agent and meta.with_name(f"{stem}.jsonl").exists():
            return meta.with_name(f"{stem}.jsonl").read_text(
                encoding="utf-8", errors="replace"
            )
    return None


def _running(book: ledger.Ledger) -> Iterable[ledger.Slot]:
    return [slot for slot in book.slots if slot.agent and not slot.waiting]


def lines(book: ledger.Ledger, root: pathlib.Path) -> Sequence[str]:
    """The ``POLLING`` lines of a ledger.

    Args:
        book: the ledger.
        root: the directory of the workers' transcripts.

    Returns:
        A line for each running agent (not waiting) whose transcript shows a
        polling loop; an agent with no transcript has none.
    """
    found: list[str] = []
    for slot in _running(book):
        text = transcript_of(root, slot.agent)
        made = calls(text) if text is not None else []
        if polls(made):
            found.append(
                f"{Marker.POLLING.text} {slot.agent} on {slot.task}: {len(made)}"
                f" tool calls, the last {LAST_CALLS} are Monitor or sleep"
            )
    return found


def print_lines(book: ledger.Ledger, root: pathlib.Path | None) -> None:
    """Print the ``POLLING`` lines of a ledger.

    Args:
        book: the ledger.
        root: the directory of the workers' transcripts, or None for none.
    """
    for line in lines(book, root) if root is not None else []:
        print(line)

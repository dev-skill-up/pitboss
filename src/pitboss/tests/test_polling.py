"""Tests of ``POLLING``: a running worker that waits by polling (pitboss#175)."""

import dataclasses
import json
import pathlib
import unittest
from typing import Mapping, Sequence

from hamcrest import assert_that, equal_to

from .. import ledger, polling
from . import fakes, test_handback, world

Call = tuple[str, str]
MARKER = "POLLING"
MONITOR = ("Monitor", "")
SLEEP = ("Bash", "sleep 295; echo tick")
READ = ("Read", "")
WORK = ("Bash", "nox -r -s tests-3.13")
NOISE = [
    json.dumps({"message": {"content": "plain text"}}),
    json.dumps({"message": {"content": [{"type": "text", "text": "hi"}]}}),
    json.dumps({"other": 1}),
    "not json",
]


def entry(name: str, command: str) -> str:
    """A transcript line with one tool call.

    Args:
        name: the tool.
        command: its command.

    Returns:
        The JSON line.
    """
    call = {"type": "tool_use", "name": name, "input": {"command": command}}
    return json.dumps({"message": {"content": [call]}})


def transcript(made: Sequence[tuple[str, str]]) -> str:
    """The text of a transcript with some tool calls among lines with none.

    Args:
        made: the tool name and command of each call.

    Returns:
        JSON lines.
    """
    return "\n".join([*NOISE, *(entry(*each) for each in made)])


def keep(
    root: pathlib.Path, agent: str, name: str, made: Sequence[tuple[str, str]]
) -> None:
    """Write the transcript and the meta file of a worker.

    Args:
        root: the directory of transcripts.
        agent: the agent id.
        name: the name in the meta file.
        made: its tool calls.
    """
    meta(root, agent, json.dumps({"name": name}))
    fakes.write(root / f"agent-{agent}.jsonl", transcript(made))


def meta(root: pathlib.Path, agent: str, text: str) -> None:
    """Write the meta file of a worker.

    Args:
        root: the directory of transcripts.
        agent: the agent id.
        text: the file's content.
    """
    fakes.write(root / f"agent-{agent}.meta.json", text)


def held(waiting: bool) -> ledger.Ledger:
    """A ledger with a slot that holds the agent ``worker``.

    Args:
        waiting: the agent waits.

    Returns:
        The ledger.
    """
    slot = test_handback.held("").slots[0]
    kept = dataclasses.replace(slot, agent="worker", task="#9", waiting=waiting)
    return dataclasses.replace(test_handback.held(""), slots=(kept,))


def runs(*each: tuple[Call, int]) -> Sequence[Call]:
    """Calls made in runs.

    Args:
        *each: a call and how many times it is made in a row.

    Returns:
        The calls, in order.
    """
    return [call for call, count in each for _ in range(count)]


POLLING_CALLS = runs((READ, 21), (MONITOR, 20))
CASES: Mapping[str, tuple[Sequence[Call], bool, int]] = {
    "polling": (POLLING_CALLS, False, 1),
    "working": (runs((MONITOR, 30), (WORK, 1), (MONITOR, 15)), False, 0),
    "waiting": (runs((MONITOR, 50)), True, 0),
}
VERDICTS: Mapping[str, tuple[Sequence[Call], bool]] = {
    "41, both waits": (runs((READ, 21), (MONITOR, 10), (SLEEP, 10)), True),
    "40": (runs((READ, 20), (MONITOR, 20)), False),
    "41, one nox run": (
        runs((READ, 30), (MONITOR, 9), (WORK, 1), (MONITOR, 10)),
        False,
    ),
}


class TestPolls(unittest.TestCase):
    """More than 40 calls, the last 20 of them only waiting."""

    def test_the_count_and_the_last_twenty(self) -> None:
        """Over 40, not 40; a call of work among the last twenty ends it."""
        for name, (made, want) in VERDICTS.items():
            with self.subTest(name):
                assert_that(polling.polls(made), equal_to(want))

    def test_only_a_sleeping_shell_call_waits(self) -> None:
        """A shell call without sleep, or another tool with it, does not."""
        found = [polling.waits(each) for each in (WORK, SLEEP, ("Read", "sleep"))]
        assert_that(found, equal_to([False, True, False]))

    def test_the_calls_of_a_transcript(self) -> None:
        """Only tool calls, in order."""
        found = polling.calls(transcript([READ, SLEEP]))
        assert_that(found, equal_to([READ, SLEEP]))


class TestLines(unittest.TestCase):
    """The lines of a ledger, read from a directory of transcripts."""

    def test_which_workers_are_named(self) -> None:
        """A polling worker is; a working or a waiting one is not."""
        for name, (made, waiting, count) in CASES.items():
            with self.subTest(name):
                root = fakes.directory()
                keep(root, "a1", "worker", made)
                found = polling.lines(held(waiting), root)
                assert_that(len(found), equal_to(count))

    def test_the_line_gives_the_agent_the_task_and_the_count(self) -> None:
        """The words of the line."""
        root = fakes.directory()
        keep(root, "a1", "worker", POLLING_CALLS)
        expected = [
            f"{MARKER} worker on #9: 41 tool calls, the last 20 are Monitor or sleep"
        ]
        assert_that(polling.lines(held(False), root), equal_to(expected))

    def test_an_agent_with_no_transcript_is_not_named(self) -> None:
        """Another agent's transcript, an unreadable meta file, a missing file."""
        root = fakes.directory()
        keep(root, "a1", "other", [MONITOR] * 50)
        meta(root, "a2", "{")
        meta(root, "a3", json.dumps({"name": "worker"}))
        assert_that(polling.lines(held(False), root), equal_to([]))
        assert_that(polling.transcript_of(root, "worker"), equal_to(None))


def swept(here: world.World) -> Sequence[str]:
    """The ``POLLING`` lines of a sweep.

    Args:
        here: the world.

    Returns:
        The lines.
    """
    printed = world.again(here, "sweep").out.splitlines()
    return [line for line in printed if line.startswith(MARKER)]


class TestSweep(unittest.TestCase):
    """The sweep prints the line when ``[slots] transcripts`` is set."""

    def test_the_line_is_printed_only_with_the_directory(self) -> None:
        """No directory, no line; a directory with a polling worker, one."""
        here = world.make_world()
        world.invoke(here, "slots", "set", here.config, "tiny", "worker", "#9", "--running", "worker")
        assert_that(swept(here), equal_to([]))
        root = here.workspace / "transcripts"
        keep(root, "a1", "worker", [MONITOR] * 45)
        path = pathlib.Path(here.config)
        owner = "ledger-owner = true"
        path.write_text(
            path.read_text().replace(owner, f'{owner}\ntranscripts = "{root}"')
        )
        assert_that(len(swept(here)), equal_to(1))

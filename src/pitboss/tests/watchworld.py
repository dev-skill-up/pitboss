"""A world that watches a tasks directory (pitboss#415)."""

import dataclasses
import pathlib
from typing import Mapping, Sequence

from .. import ledger
from . import quietworld, world
from .test_handback import slots
from .transcripts import write

NOW = "2030-01-01T00:00:00+00:00"
RECENT = "2029-12-31T23:59:00Z"
LONG_AGO = "2029-12-31T20:00:00Z"
QUIET = "2029-12-31T13:00:00Z"
OLD = "2029-12-30T10:00:00Z"
PROCESS = "2029-12-31T12:00:00+00:00"
GOAL = "WORKER: x\nGoal: ticket owner/project#{n}: A ticket\nTask: do it\n"
MARKED = "PITBOSS-SLOT: owner/project#9 fix\nthe rest mentions SubagentHandback\n"
FREED = "LEDGER CHANGED: slot tiny freed from a1 (owner/project#9): {}"
TAKES = "LEDGER CHANGED: slot tiny takes a1 on {}"
Records = Sequence[Mapping[str, object]]


def watched(extra: str = "") -> tuple[world.World, pathlib.Path]:
    """A world whose configuration names a tasks directory.

    Args:
        extra: more keys of ``[slots]``.

    Returns:
        The world and the directory.
    """
    here = world.make_world()
    directory = here.workspace / "tasks"
    keys = f'[slots]\nagents-dir = "{directory}"\n{extra}'
    quietworld.edit_config(here, "[slots]", keys)
    return here, directory


def planted(
    files: Mapping[str, Sequence[Mapping[str, object]]], extra: str = ""
) -> world.World:
    """A watched world with these transcripts written.

    Args:
        files: each agent id and the records of its transcript.
        extra: more keys of ``[slots]``.

    Returns:
        The world.
    """
    here, directory = watched(extra)
    for agent, records in files.items():
        write(directory, agent, records)
    return here


def planted_each(extras: Sequence[str]) -> Sequence[world.World]:
    """A watched world for each set of extra ``[slots]`` keys.

    Args:
        extras: the keys of each world.

    Returns:
        The worlds, in order.
    """
    return [planted({}, each) for each in extras]


def watch(
    here: world.World, rounds: str = "1", seconds: str = "0", start: str = PROCESS
) -> world.Result:
    """Run ``slots watch`` for some rounds at the fixed time.

    Args:
        here: the world.
        rounds: how many.
        seconds: the interval between them.
        start: when the Claude process started.

    Returns:
        What it did.
    """
    words = ("watch", "--rounds", rounds, "--interval", seconds, "--now", NOW)
    return slots(here, *words, "--process-start", start)


def held(here: world.World) -> Sequence[str]:
    """The agents the ledger file holds.

    Args:
        here: the world.

    Returns:
        Their names, for each row that has one.
    """
    return [each.agent for each in ledger.read(here.ledger, ()).slots if each.agent]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Clock:
    """The two times a play depends on.

    Attributes:
        when: the time the ledger rows are put in.
        start: when the Claude process started.
    """

    when: str = NOW
    start: str = PROCESS


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Left:
    """What a play of the watcher left behind.

    Attributes:
        out: what it printed.
        held: the agents the ledger holds after it.
        kinds: the kind of each row that holds one.
    """

    out: str
    held: Sequence[str]
    kinds: Sequence[str]


def play(
    files: Mapping[str, Sequence[Mapping[str, object]]],
    rows: Sequence[tuple[str, str, str]] = (),
    rounds: str = "1",
    clock: Clock = Clock(),
) -> Left:
    """Plant ledger rows and transcripts, and watch some rounds.

    Args:
        files: each agent id and the records of its transcript.
        rows: each slot, agent and pull request or ticket to put in the ledger
            at the time ``when``.
        rounds: how many rounds.
        clock: the time the rows are put in and the start of the Claude process.

    Returns:
        What the watcher printed and left in the ledger.
    """
    here, directory = watched()
    for slot, agent, task in rows:
        slots(here, "set", slot, agent, task, "--running", agent, "--now", clock.when)
    for agent, records in files.items():
        write(directory, agent, records)
    out = watch(here, rounds, start=clock.start).out
    kept = [each for each in ledger.read(here.ledger, ()).slots if each.agent]
    return Left(out=out, held=held(here), kinds=[each.kind for each in kept])

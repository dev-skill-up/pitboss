"""A log of the commands a sweep ran and how long each took (keyword: call-log).

The sweep's phases are slow for what they wait for: a ``gh api`` call, a ``git
fetch``. The log wraps the runner the sweep reads through, so each phase can
say how many calls it made and, when it is slow, which ones it waited for.
"""

import collections
import dataclasses
import re
import threading
import time
from typing import Callable, Mapping, Sequence

from .running import Output, Run

NAME_LIMIT = 110


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Call:
    """One command that ran.

    Attributes:
        name: the command line, cut short.
        kind: what it asked for (``gh api pulls``), to count alike calls.
        seconds: how long it took.
    """

    name: str
    kind: str
    seconds: float


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Phase:
    """What a phase of the sweep ran.

    Attributes:
        seconds: how long the phase took.
        calls: the commands it ran, in the order they finished.
    """

    seconds: float
    calls: Sequence[Call]


class Log:
    """The commands run since the last phase ended; calls may come from threads."""

    def __init__(self, started: float) -> None:
        """Start a log.

        Args:
            started: when the first phase began (monotonic seconds).
        """
        self.lock = threading.Lock()
        self.calls: list[Call] = []
        self.phase_started = started

    def add(self, call: Call) -> None:
        """Record a finished command.

        Args:
            call: the command.
        """
        with self.lock:
            self.calls.append(call)

    def end_phase(self, now: float) -> Phase:
        """Hand over the commands of the phase that ends now, and start the next.

        Args:
            now: the time now (monotonic seconds).

        Returns:
            The phase.
        """
        with self.lock:
            phase = Phase(seconds=now - self.phase_started, calls=tuple(self.calls))
            self.calls.clear()
            self.phase_started = now
            return phase


def name_of(command: Sequence[str]) -> str:
    """Say a command line in one short piece.

    Args:
        command: the command line.

    Returns:
        The line, cut to ``NAME_LIMIT`` characters.
    """
    text = " ".join(command)
    return text if len(text) <= NAME_LIMIT else text[: NAME_LIMIT - 3] + "..."


def kind_of(command: Sequence[str]) -> str:
    """Say what a command asks for, without the repository or the numbers.

    ``gh api repos/o/r/pulls/12/reviews?per_page=100`` is ``gh api
    pulls/reviews``; any other command is its first two words.

    Args:
        command: the command line.

    Returns:
        The kind.
    """
    if list(command[:2]) != ["gh", "api"]:
        return " ".join(command[:2])
    path = command[-1].split("?", 1)[0]
    words = [
        each
        for each in path.split("/")[3:]
        if not each.isdigit() and not re.fullmatch(r"[0-9a-f]{40}", each)
    ]
    return "gh api " + "/".join(words)


def tally(phase: Phase) -> Mapping[str, int]:
    """Count a phase's commands by kind.

    Args:
        phase: the phase.

    Returns:
        Each kind and its count, the most numerous first.
    """
    counts = collections.Counter(each.kind for each in phase.calls)
    return dict(counts.most_common())


def timed(
    run: Run, log: Log, clock: Callable[[], float] = time.monotonic
) -> Run:
    """Wrap a runner so that every command it runs is logged.

    A command that raises is logged too: the time it took is the time waited.

    Args:
        run: the runner.
        log: the log.
        clock: the monotonic clock.

    Returns:
        The runner that logs.
    """

    def logged(cmdargs: Sequence[str], /) -> Output:
        began = clock()
        try:
            return run(cmdargs)
        finally:
            log.add(
                Call(
                    name=name_of(cmdargs),
                    kind=kind_of(cmdargs),
                    seconds=clock() - began,
                )
            )

    return logged


def slowest(phase: Phase, count: int) -> Sequence[Call]:
    """The commands that took longest in a phase.

    Args:
        phase: the phase.
        count: the most commands.

    Returns:
        The commands, slowest first.
    """
    return sorted(phase.calls, key=lambda each: each.seconds, reverse=True)[:count]

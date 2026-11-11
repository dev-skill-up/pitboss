"""A log of the commands a sweep ran and how long each took (keyword: call-log).

The sweep's phases are slow for what they wait for: a ``gh api`` call, a ``git
fetch``. The log wraps the runner the sweep reads through, so each phase can
say how many calls it made and, when it is slow, which ones it waited for.
"""

import collections
import contextlib
import dataclasses
import re
import threading
import time
from typing import Callable, Mapping, MutableSequence, Sequence

from .running import KeywordRun, Output

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


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Log:
    """The commands run since the last phase ended; calls may come from threads.

    Attributes:
        lock: held while the log changes.
        calls: the commands of the phase that is running.
        began: the start of that phase (monotonic seconds), as the one item.
    """

    lock: threading.Lock
    calls: MutableSequence[Call]
    began: MutableSequence[float]


def new_log(started: float) -> Log:
    """A log whose first phase begins now.

    Args:
        started: when the first phase began (monotonic seconds).

    Returns:
        The log.
    """
    return Log(lock=threading.Lock(), calls=[], began=[started])


def add(log: Log, call: Call) -> None:
    """Record a finished command.

    Args:
        log: the log.
        call: the command.
    """
    with log.lock:
        log.calls.append(call)


def end_phase(log: Log, now: float) -> Phase:
    """Hand over the commands of the phase that ends now, and start the next.

    Args:
        log: the log.
        now: the time now (monotonic seconds).

    Returns:
        The phase.
    """
    with log.lock:
        phase = Phase(seconds=now - log.began[0], calls=tuple(log.calls))
        log.calls.clear()
        log.began[0] = now
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
    return "gh api " + ("/".join(words) or "repository")


def tally(phase: Phase) -> Mapping[str, int]:
    """Count a phase's commands by kind.

    Args:
        phase: the phase.

    Returns:
        Each kind and its count, the most numerous first.
    """
    counts = collections.Counter(each.kind for each in phase.calls)
    return dict(counts.most_common())


def record(log: Log, command: Sequence[str], began: float, now: float) -> None:
    """Record a command that ended.

    Args:
        log: the log.
        command: the command line.
        began: when it began (monotonic seconds).
        now: when it ended (monotonic seconds).
    """
    call = Call(name=name_of(command), kind=kind_of(command), seconds=now - began)
    add(log, call)


def logging_run(
    run: KeywordRun, log: Log, clock: Callable[[], float] = time.monotonic
) -> KeywordRun:
    """Wrap a runner so that every command it runs is logged.

    A command that raises is logged too: the time it took is the time waited.
    Every positional and keyword argument of a call (``check=True``,
    ``cwd=...``) goes on to the runner as it came (keyword: call-log).

    Args:
        run: the runner, which takes what the callers of ``safe_run`` pass.
        log: the log.
        clock: the monotonic clock.

    Returns:
        The runner that logs.
    """

    def logged(command: Sequence[str], /, *args: object, **kwargs: object) -> Output:
        with contextlib.ExitStack() as stack:
            stack.callback(lambda: record(log, command, began, clock()))
            began = clock()
            return run(command, *args, **kwargs)

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

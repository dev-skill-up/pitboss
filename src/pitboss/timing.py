"""Per-section timing of a sweep, on stderr."""

import argparse
import dataclasses
import datetime
import sys
import time
from typing import Callable, MutableSequence, Sequence

from . import breakdown, calllog

REST_SECONDS = 0.1
SLOW_SECONDS = 30
NAMED_CALLS = 5


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Clock:
    """Per-section timing, on stderr.

    Attributes:
        started: when the command started (monotonic seconds).
        log: the commands the sweep ran, which a slow section names.
        sections: the sections that ended, for the breakdown (keyword:
            timing-lines).
        read: the monotonic clock (a test gives its own).
    """

    started: float
    log: calllog.Log
    sections: MutableSequence[breakdown.Section] = dataclasses.field(
        default_factory=list
    )
    read: Callable[[], float] = time.monotonic


def start(read: Callable[[], float] = time.monotonic) -> Clock:
    """Start the clock of a command.

    Args:
        read: the monotonic clock.

    Returns:
        The clock.
    """
    now = read()
    return Clock(started=now, log=calllog.new_log(now), read=read)


def logged_args(args: argparse.Namespace, clock: Clock) -> argparse.Namespace:
    """The arguments with a reading runner that logs every command it runs.

    Args:
        args: the parsed arguments.
        clock: the clock whose log takes the commands.

    Returns:
        A copy of the arguments whose ``safe_run`` logs, and the ``clock``.
    """
    logging_run = calllog.logging_run(args.safe_run, clock.log, clock.read)
    return argparse.Namespace(**{**vars(args), "safe_run": logging_run, "clock": clock})


def mark(clock: Clock, section: str, count: int = 0, noun: str = "") -> calllog.Phase:
    """End a section without saying anything: the breakdown tells it at the end.

    Args:
        clock: the clock.
        section: the section that just finished.
        count: how many things it worked on, 0 for none.
        noun: what the count counts.

    Returns:
        The section: how long it took and the commands it ran.
    """
    phase = calllog.end_phase(clock.log, clock.read())
    clock.sections.append(
        breakdown.Section(name=section, count=count, noun=noun, phase=phase)
    )
    return phase


def note(
    args: argparse.Namespace, section: str, count: int = 0, noun: str = ""
) -> None:
    """End a section of the breakdown, when the command keeps one.

    Args:
        args: the parsed arguments; without a ``clock`` nothing is noted.
        section: the section that just finished.
        count: how many things it worked on, 0 for none.
        noun: what the count counts.
    """
    clock = getattr(args, "clock", None)
    if clock is not None:
        mark(clock, section, count, noun)


def lap(clock: Clock, section: str) -> None:
    """Say on stderr how long the command has run and what the section ran.

    A section that took more than ``SLOW_SECONDS`` also names the commands it
    waited longest for. The lines printed so far are flushed first, so a caller
    that reads a pipe sees each section as it ends.

    Args:
        clock: the clock.
        section: the section that just finished.
    """
    sys.stdout.flush()  # a pipe holds the lines back otherwise
    phase = mark(clock, section)
    now = clock.read()
    print(
        f"[pitboss {now - clock.started:.0f}s] {section}:"
        f" {phase.seconds:.0f}s, {len(phase.calls)} commands",
        file=sys.stderr,
        flush=True,
    )
    counts = ", ".join(f"{kind} {each}" for kind, each in calllog.tally(phase).items())
    if counts:
        print(f"  ran: {counts}", file=sys.stderr)
    if phase.seconds <= SLOW_SECONDS:
        return
    for call in calllog.slowest(phase, NAMED_CALLS):
        print(f"  waited {call.seconds:.1f}s for {call.name}", file=sys.stderr)


def current_time(args: argparse.Namespace) -> datetime.datetime:
    """The time now, or the time ``--now`` gives.

    Args:
        args: the parsed arguments.

    Returns:
        The time.
    """
    if args.now:
        return datetime.datetime.fromisoformat(args.now)
    return datetime.datetime.now(datetime.timezone.utc)


def clocked(args: argparse.Namespace) -> tuple[Clock, argparse.Namespace]:
    """The clock of a command and the arguments that log, made once.

    Args:
        args: the parsed arguments; a command that ends with its breakdown has
            a ``clock`` already (keyword: timing-lines).

    Returns:
        That clock and the arguments, else a new clock and arguments that log.
    """
    clock = getattr(args, "clock", None)
    if clock is not None:
        return clock, args
    started = start()
    return started, logged_args(args, started)


def finish(clock: Clock, command: str, startup: float | None) -> Sequence[str]:
    """The lines that end a command (keyword: timing-lines, pitboss#443).

    What ran after the last section is a section of its own, ``rest``, when it
    ran a command or took a tenth of a second.

    Args:
        clock: the clock.
        command: the command, as typed.
        startup: the seconds before the command started, None when unknown.

    Returns:
        The breakdown's lines.
    """
    now = clock.read()
    rest = calllog.end_phase(clock.log, now)
    if rest.calls or rest.seconds >= REST_SECONDS:
        clock.sections.append(
            breakdown.Section(name="rest", count=0, noun="", phase=rest)
        )
    return breakdown.lines(command, clock.sections, now - clock.started, startup)

"""Per-section timing of a sweep, on stderr."""

import argparse
import dataclasses
import datetime
import sys
import time

from . import calllog

SLOW_SECONDS = 30
NAMED_CALLS = 5


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Clock:
    """Per-section timing, on stderr.

    Attributes:
        started: when the command started (monotonic seconds).
        log: the commands the sweep ran, which a slow section names.
    """

    started: float
    log: calllog.Log


def start() -> Clock:
    """Start the clock of a command.

    Returns:
        The clock.
    """
    now = time.monotonic()
    return Clock(started=now, log=calllog.new_log(now))


def logged_args(args: argparse.Namespace, clock: Clock) -> argparse.Namespace:
    """The arguments with a reading runner that logs every command it runs.

    Args:
        args: the parsed arguments.
        clock: the clock whose log takes the commands.

    Returns:
        A copy of the arguments whose ``safe_run`` logs.
    """
    logging_run = calllog.logging_run(args.safe_run, clock.log)
    return argparse.Namespace(**{**vars(args), "safe_run": logging_run})


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
    now = time.monotonic()
    phase = calllog.end_phase(clock.log, now)
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

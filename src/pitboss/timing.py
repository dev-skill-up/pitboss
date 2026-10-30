"""Per-section timing of a sweep, on stderr."""

import argparse
import dataclasses
import datetime
import sys
import time


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Clock:
    """Per-section timing, on stderr.

    Attributes:
        started: when the command started (monotonic seconds).
    """

    started: float


def lap(clock: Clock, section: str) -> None:
    """Say on stderr how long the command has run.

    Args:
        clock: the clock.
        section: the section that just finished.
    """
    print(
        f"[pitboss {time.monotonic() - clock.started:.0f}s] {section}", file=sys.stderr
    )


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

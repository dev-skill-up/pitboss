"""The check-in lines every sweep starts with, and ``status-prompt`` (check-in)."""

import argparse
from typing import Callable

from . import (
    ENTRY_DATA,
    checkin,
    configfile,
    ledger,
    nextfound,
)
from .commandarguments import CONFIG_ARGUMENT


def print_first(found: nextfound.Found, idle: Callable[[], str | None]) -> bool:
    """Print ``CHECK-IN OVERDUE``, then ``IDLE SLOT``, when each applies.

    Args:
        found: the context.
        idle: says the ``IDLE SLOT`` line, or None when it does not apply.

    Returns:
        True when the check-in is overdue, which fails the sweep.
    """
    late = checkin.overdue(ledger.configured(found.settings), found.now)
    checkin.say((late, idle()))
    return late is not None


@ENTRY_DATA.register(CONFIG_ARGUMENT, name="status-prompt")
def status_prompt(args: argparse.Namespace) -> None:
    """Print the orchestrator's check-in prompt: the 30-minute status post.

    Args:
        args: the parsed arguments.
    """
    print(checkin.PROMPT.replace("CONFIG", configfile.named(args)), end="")

"""The check-in lines every sweep starts with, and ``status-prompt`` (check-in)."""

import argparse
from typing import Callable

from . import (
    ENTRY_DATA,
    checkin,
    configfile,
    freecheck,
    ledger,
    nextfound,
)
from .commandarguments import CONFIG_ARGUMENT


def print_first(found: nextfound.Found, first: Callable[[], str]) -> bool:
    """Print ``CHECK-IN OVERDUE``, then ``IDLE SLOT``, when each applies.

    Args:
        found: the context.
        first: says the first startable item (``IDLE SLOT`` names it).

    Returns:
        True when the check-in is overdue, which fails the sweep.
    """
    late = checkin.overdue(ledger.configured(found.settings), found.now)
    checkin.say((late, freecheck.line(found, ledger.configured(found.settings), first)))
    return late is not None


@ENTRY_DATA.register(CONFIG_ARGUMENT, name="status-prompt")
def status_prompt(args: argparse.Namespace) -> None:
    """Print the orchestrator's check-in prompt: the 30-minute status post.

    Args:
        args: the parsed arguments.
    """
    print(checkin.PROMPT.replace("CONFIG", configfile.named(args)), end="")

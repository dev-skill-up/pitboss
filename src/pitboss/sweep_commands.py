"""The ``sweep`` command: the check-in lines first, then the sections."""

import argparse
import functools

from . import ENTRY_DATA, checkinlines, commanddoc, commandtext, freecheck
from . import nextlist, tasklist, timing
from .commandarguments import SWEEP_ARGUMENTS
from .commands import load_context, open_pulls, sweep_sections


@ENTRY_DATA.register(*SWEEP_ARGUMENTS, tasklist.ARGUMENT, name="sweep")
@commanddoc.described(commandtext.SWEEP)
def sweep(args: argparse.Namespace) -> None:
    """Report on PRs, runner pressure, queue runs, stragglers, worktrees, slots, LOG.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 for a failed check, a conflict, an unread repository, or a
            check-in that is overdue.
    """
    clock, args = timing.clocked(args)
    found = load_context(args)
    opened = functools.partial(open_pulls, found)
    idle = functools.partial(freecheck.line, found, opened, nextlist.first_startable)
    lapsed = checkinlines.print_first(found, idle)
    if sweep_sections(found, clock) or lapsed:
        raise SystemExit(1)

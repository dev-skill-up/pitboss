"""The ``sweep`` command: the check-in lines first, then the sections."""

import argparse
import functools

from . import ENTRY_DATA, checkinlines, commanddoc, commandtext, freecheck
from . import onepath, tasklist, timing
from .commandarguments import SWEEP_ARGUMENTS
from .commands import load_context, sweep_sections


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
    # keyword: one-path: one read; the check-in's first line and the sections share it
    seen = onepath.seen_for(found)
    idle = functools.partial(freecheck.line, found, lambda _: onepath.first_of(seen))
    lapsed = checkinlines.print_first(found, idle)
    if sweep_sections(found, clock, seen) or lapsed:
        raise SystemExit(1)

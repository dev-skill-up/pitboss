"""The ``clean`` command: the cleaning a sweep does first, run on its own."""

import argparse

from gather.commands import add_argument

from . import ENTRY_DATA, autoclean, machine as machines
from .commands import (
    CONFIG_ARGUMENT,
    NOW_ARGUMENT,
    load_context,
    running_in,
    sweep_look,
)


@ENTRY_DATA.register(
    CONFIG_ARGUMENT,
    NOW_ARGUMENT,
    add_argument("--dry-run", action="store_true", default=False),
    name="clean",
)
def clean(args: argparse.Namespace) -> None:
    """Clean the disk now, as a sweep does first; nothing to confirm.

    It removes the test tempdirs older than ``[clean] tmp_hours``, the finished
    worktrees and the dead checkouts, and, with the disk at ``[clean]
    pressure_percent`` used or more, every worktree and checkout without an open
    PR and the package caches that regenerate. It never touches a worktree with
    an open PR or a running worker's directory. ``--dry-run`` removes nothing.
    This is the answer to a denied ``rm``: run it, do not stop (keyword:
    auto-clean).

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    run = args.run if args.dry_run else args.safe_run
    option = autoclean.Option(run=run, dry=args.dry_run)
    machine = machines.real_machine(args.env, found.now, running_in(args))
    for text in autoclean.clean_lines(sweep_look(found), machine, option):
        print(text)

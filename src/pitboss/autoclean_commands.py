"""The ``clean`` command: the cleaning a sweep does first, run on its own."""

import argparse

from gather.commands import add_argument

from . import ENTRY_DATA, autoclean, cleanjob, logline, machine as machines, scratch
from .commandarguments import CONFIG_ARGUMENT, NOW_ARGUMENT
from .commands import load_context, running_in, sweep_look


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
    pressure_percent`` used or more, or less than ``[clean] min_free_gib``
    free, every worktree and checkout without an open
    PR and the package caches that regenerate. It never touches a worktree with
    an open PR or a running worker's directory. It also closes the open PRs of the
    ``[scratch]`` repositories whose workflow runs finished, except the kept
    fixtures, and deletes their branches. ``--dry-run`` removes and closes
    nothing, and lists those PRs instead.
    This is the answer to a denied ``rm``: run it, do not stop (keyword:
    auto-clean).

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    run = args.run if args.dry_run else args.safe_run
    option = cleanjob.Option(run=run, dry=args.dry_run)
    machine = machines.real_machine(args.env, found.now, running_in(args), args.usage)
    done = autoclean.clean_report(sweep_look(found), machine, option)
    for text in done.lines:
        print(text)
    if not args.dry_run:
        freed = sum(done.told.freed)
        event = logline.clean_up("pitboss clean", freed, done.told.heads, found.now)
        logline.record(found.settings.slots.log, event)
    source = scratch.source_of(args.safe_run, found.scratch, found.now)
    for text in (scratch.listing if args.dry_run else scratch.cleaning)(source):
        print(text)

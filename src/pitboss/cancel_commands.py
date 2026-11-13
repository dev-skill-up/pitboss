"""The ``cancel-stale-runs`` command: cancel the queue runs that are stale."""

import argparse
import subprocess

from . import ENTRY_DATA, queue
from .commandarguments import CHANGING_ARGUMENTS
from .commands import load_context
from .markers import Marker
from .queuereads import cancel, read_queue_runs


@ENTRY_DATA.register(*CHANGING_ARGUMENTS, name="cancel-stale-runs")
def cancel_stale_runs(args: argparse.Namespace) -> None:
    """Cancel the queue runs that are not the newest group of their PR.

    Args:
        args: the parsed arguments.
    """
    found = load_context(args)
    verb = "" if args.no_dry_run else " (dry run: --no-dry-run cancels it)"
    for stale in queue.stale_runs(read_queue_runs(found)):
        name = f"{stale.repo.slug} {stale.run.id}"
        try:
            cancel(found, stale)
        except subprocess.CalledProcessError:
            print(f"{Marker.COULD_NOT_CANCEL_STALE_QUEUE_RUN.text} {name}")
            continue
        print(f"{Marker.CANCELLED_STALE_QUEUE_RUN.text} {name}{verb}")

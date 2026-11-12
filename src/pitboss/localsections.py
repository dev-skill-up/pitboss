"""The sweep's sections that read this machine (keyword: local-sections)."""

import pathlib

from . import __version__, concurrently, local, orphanline, outdated, tracefs
from .running import Run


def print_update_check(run: Run) -> None:
    """Say whether the tracing file system is there and whether pitboss is old.

    Args:
        run: the runner for reads.
    """
    tracefs.say(run)
    for line in outdated.lines(__version__, outdated.newest(run)):
        print(line)


def straggler_line(run: Run, checkout: pathlib.Path) -> str | None:
    """Say what a checkout holds that is not on its remote.

    Args:
        run: the runner for reads.
        checkout: the checkout.

    Returns:
        The line; None for a checkout that holds nothing of the kind.
    """
    if local.orphaned(run, checkout):
        return orphanline.orphan_line(checkout)
    straggler = local.read_straggler(run, checkout)
    return None if straggler is None else orphanline.straggler_line(straggler)


def print_stragglers(run: Run, workspace: pathlib.Path) -> None:
    """Print the stragglers of the checkouts under the workspace.

    The checkouts are read at once, and printed in their order.

    Args:
        run: the runner for reads.
        workspace: the directory that holds the checkouts.
    """
    found = local.checkouts(workspace)
    for failed in local.fetch_each_repository(run, found):
        print(f"fetch failed in {failed}: its stragglers may be out of date")
    for line in concurrently.each(lambda each: straggler_line(run, each), found):
        if line is not None:
            print(line)
    print("stragglers: sweep done")

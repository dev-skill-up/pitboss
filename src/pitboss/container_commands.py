"""The ``clean-container`` command: remove files written well after the start."""

import argparse
import pathlib

from gather.commands import add_argument

from . import ENTRY_DATA, container
from .commands import DRY_RUN_ARGUMENT


@ENTRY_DATA.register(
    add_argument("--marker", default="/container_info.json"),
    add_argument("--root", default="/"),
    add_argument("--hours", type=float, default=1.0),
    DRY_RUN_ARGUMENT,
    name="clean-container",
)
def clean_container(args: argparse.Namespace) -> None:
    """Remove the regular files in the root written well after the start.

    A file counts when it was modified more than ``--hours`` after the
    marker. Only regular files directly in ``--root`` are removed: no
    subdirectories, symbolic links or anything else.

    Args:
        args: the parsed arguments.
    """
    marker = pathlib.Path(args.marker)
    after = container.cutoff(marker, args.hours)
    verb = "" if args.no_dry_run else " (dry run: --no-dry-run removes it)"
    found = container.newer_files(pathlib.Path(args.root), after)
    for each in found:
        if args.no_dry_run:
            each.path.unlink(missing_ok=True)
        print(f"removed {each.path}{verb}")
    size = sum(each.size for each in found)
    print(f"container: {len(found)} files, {size / 2**20:.1f} MiB")

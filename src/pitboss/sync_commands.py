"""The ``sync`` command: keep the working files in a repository's main."""

import argparse
import sys

from . import ENTRY_DATA
from . import configfile, syncing
from .commands import CONFIG_ARGUMENT, NOW_ARGUMENT, load_settings


@ENTRY_DATA.register(CONFIG_ARGUMENT, NOW_ARGUMENT, name="sync")
def sync(args: argparse.Namespace) -> None:
    """Copy the files outside any repository to ``[sync]``'s repository, on main.

    The configuration, the slot ledger and log, the pressure record and the
    ``[sync] paths`` are copied under ``[sync] directory`` (each at its own
    absolute path), committed and pushed straight to main. It prints a line for
    each file that changed and nothing when none did; a sweep does the same at
    its end (keyword: sync).

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 2 when the configuration has no ``[sync]`` table, 1 when a
            file is missing or git failed.
    """
    settings = load_settings(args)
    start = configfile.working_directory(args)
    if configfile.load_sync(args.config, start, start) is None:
        print("the configuration has no [sync] table", file=sys.stderr)
        raise SystemExit(2)
    if syncing.section(args, settings):
        raise SystemExit(1)

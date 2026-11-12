"""The sweep's lines about the workers the ledger holds."""

import argparse
import datetime

from . import config, configfile, configloads, handback, ledger, polling, watchbeat


def print_lines(
    book: ledger.Ledger,
    now: datetime.datetime,
    args: argparse.Namespace,
    slots: config.Slots,
) -> None:
    """Print the ``NO HAND-BACK`` lines and, with transcripts, the ``POLLING`` ones.

    Args:
        book: the ledger.
        now: the time now.
        args: the parsed arguments, which name the configuration.
        slots: the slot configuration; a tasks directory asks for a watcher.
    """
    handback.print_lines(book, now)
    root = configloads.load_transcripts(
        configfile.named(args), configfile.working_directory(args)
    )
    polling.print_lines(book, root)
    if slots.watch.agents_dir is not None:
        for said in watchbeat.missing_line(slots.ledger, now, configfile.named(args)):
            print(said)

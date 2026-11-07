"""The sweep's lines about the workers the ledger holds."""

import argparse
import datetime

from . import configfile, handback, ledger, polling


def print_lines(
    book: ledger.Ledger, now: datetime.datetime, args: argparse.Namespace
) -> None:
    """Print the ``NO HAND-BACK`` lines and, with transcripts, the ``POLLING`` ones.

    Args:
        book: the ledger.
        now: the time now.
        args: the parsed arguments, which name the configuration.
    """
    handback.print_lines(book, now)
    root = configfile.load_transcripts(
        configfile.named(args), configfile.working_directory(args)
    )
    polling.print_lines(book, root)

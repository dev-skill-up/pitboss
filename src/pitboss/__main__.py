"""Run pitboss as ``python -m pitboss``."""

import logging
import sys

from gather import commands as gather_commands

from . import ENTRY_DATA, cli_parser

if __name__ == "__main__":
    # gather's ``entry.dunder_main`` builds its own parser, so its steps are here.
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s:%(levelname)s:%(name)s:%(message)s")
    )
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    gather_commands.run_maybe_dry(
        parser=cli_parser.make_parser(),
        is_subcommand=False,
        prefix=ENTRY_DATA.prefix,
        argv=sys.argv,
    )

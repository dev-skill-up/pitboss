"""The ``quiesce`` command: stop ``slots next`` from offering work (D11)."""

import argparse

from gather.commands import add_argument

from . import ENTRY_DATA, commands, quiesce
from .commandarguments import CONFIG_ARGUMENT


@ENTRY_DATA.register(
    add_argument("state", choices=("on", "off"), help="on: offer nothing; off: lift"),
    CONFIG_ARGUMENT,
    name="quiesce",
)
def quiesce_command(args: argparse.Namespace) -> None:
    """Switch the quiesce on or off and print the new state.

    While it is on ``slots next`` prints ``QUIESCED`` and offers no NEXT line, no
    brief and no empty slot, and ``slots next ITEM`` answers UNKNOWN; the record
    is a file beside the ledger (keyword: quiesce).

    Args:
        args: the parsed arguments.
    """
    ledger = commands.load_settings(args).slots.ledger
    print(quiesce.set_to(ledger, args.state == "on"))

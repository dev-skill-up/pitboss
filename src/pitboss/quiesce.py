"""Quiesce: nothing starts until the owner lifts it (D11, keyword: quiesce).

Owner, 2026-10-31: when the owner quiesces the work, no new work starts until he
lifts it. ``pitboss quiesce on`` writes a file beside the ledger; while it is
there ``slots next`` offers no start, no brief and no empty slot, and says so.
``pitboss quiesce off`` removes it.
"""

import pathlib

from . import directories

NAME = "quiesced"
LINE = (
    "QUIESCED: nothing starts until the owner lifts it (pitboss quiesce off): no"
    " NEXT line, no brief, no empty slot"
)
REFUSED = "UNKNOWN: {reference} is not offered: " + LINE


def is_on(ledger: pathlib.Path) -> bool:
    """Whether work is quiesced.

    Args:
        ledger: the ledger's file.

    Returns:
        True when the record exists.
    """
    return ledger.with_name(NAME).exists()


def switch_on(ledger: pathlib.Path) -> str:
    """Switch the quiesce on.

    Args:
        ledger: the ledger's file.

    Returns:
        The line that says it is on.
    """
    directories.made(ledger.parent)
    ledger.with_name(NAME).touch()
    return LINE


def switch_off(ledger: pathlib.Path) -> str:
    """Switch the quiesce off.

    Args:
        ledger: the ledger's file.

    Returns:
        The line that says it is off.
    """
    ledger.with_name(NAME).unlink(missing_ok=True)
    return "quiesce is off: slots next offers work again"


def say(ledger: pathlib.Path) -> bool:
    """Print the quiesce line when work is quiesced.

    Args:
        ledger: the ledger's file.

    Returns:
        Whether work is quiesced, so that nothing else is offered.
    """
    quiesced = is_on(ledger)
    if quiesced:
        print(LINE)
    return quiesced

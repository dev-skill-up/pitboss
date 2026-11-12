"""Quiesce: nothing starts until the owner lifts it (D11, keyword: quiesce).

Owner, 2026-10-31: when the owner quiesces the work, no new work starts until he
lifts it. ``pitboss quiesce on`` writes a file beside the ledger; while it is
there ``slots next`` offers no start, no brief and no empty slot, and says so.
``pitboss quiesce off`` removes it.
"""

import pathlib

NAME = "quiesced"
LINE = (
    "QUIESCED: nothing starts until the owner lifts it (pitboss quiesce off): no"
    " NEXT line, no brief, no empty slot"
)
REFUSED = "UNKNOWN: {reference} is not offered: " + LINE


def path_of(ledger: pathlib.Path) -> pathlib.Path:
    """Where the quiesce record of a ledger is.

    Args:
        ledger: the ledger's file.

    Returns:
        The record's file, beside it.
    """
    return ledger.with_name(NAME)


def is_on(ledger: pathlib.Path) -> bool:
    """Whether work is quiesced.

    Args:
        ledger: the ledger's file.

    Returns:
        True when the record exists.
    """
    return path_of(ledger).exists()


def set_to(ledger: pathlib.Path, on: bool) -> str:
    """Switch the quiesce on or off.

    Args:
        ledger: the ledger's file.
        on: the new state.

    Returns:
        The line that says the new state.
    """
    target = path_of(ledger)
    if on:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("quiesced\n", encoding="utf-8")
        return LINE
    target.unlink(missing_ok=True)
    return "quiesce is off: slots next offers work again"

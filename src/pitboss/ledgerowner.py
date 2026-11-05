"""Which configuration owns the slot ledger (keyword: ledger-owner).

Two configurations may name the same ledger file and each print a plausible
list of what to start next; only the orchestrator's refills a slot.
"""

import pathlib

from . import config, ledger
from .markers import Marker

UNRECORDED = "the configuration with ledger-owner = true"


def owner(settings: config.Config, path: pathlib.Path) -> str | None:
    """Say which configuration to use when ``path`` does not own the ledger.

    The configuration owns the ledger when it sets ``ledger-owner = true`` in
    ``[slots]``, or when the ledger file records its path. Only the path the
    file records is read; the slots are not. A ledger file that does not exist
    has no owner yet (``LEDGER MISSING`` says so).

    Args:
        settings: the configuration.
        path: the configuration file that was given.

    Returns:
        None when ``path`` owns the ledger, else the recorded path, or
        ``UNRECORDED`` when the file records none.
    """
    if settings.slots.ledger_owner or not settings.slots.ledger.exists():
        return None
    recorded = ledger.recorded_config(settings.slots.ledger)
    if recorded and pathlib.Path(recorded).resolve() == path.resolve():
        return None
    return recorded or UNRECORDED


def refusal(use: str) -> str:
    """The line a ``slots`` command prints when it is refused.

    Args:
        use: the configuration to use (from ``owner``).

    Returns:
        The line.
    """
    return f"not the orchestrator config: use {use}"


def say_sweep(settings: config.Config, path: pathlib.Path) -> None:
    """Print the first line of a sweep of a configuration that is not the owner.

    Args:
        settings: the configuration.
        path: the configuration file that was given.
    """
    use = owner(settings, path)
    if use is not None:
        print(sweep_line(use))


def sweep_line(use: str) -> str:
    """The first line of a sweep of a configuration that does not own the ledger.

    Args:
        use: the configuration to use (from ``owner``).

    Returns:
        The line.
    """
    return (
        f"{Marker.NOT_THE_ORCHESTRATOR_CONFIG.text}: the slots and NEXT lines of"
        f" this sweep are not the orchestrator list: use {use}"
    )

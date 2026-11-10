"""The part of a command's context that the list reads (keyword: next-list)."""

import argparse
import datetime
import pathlib
import sys
from typing import Protocol

from . import cleanconfig, config, ghapi


class Found(Protocol):
    """The part of a command's context that the list reads."""

    @property
    def github(self) -> ghapi.GitHub:
        """The API.

        Returns:
            The API.
        """

    @property
    def settings(self) -> config.Config:
        """The configuration.

        Returns:
            The configuration.
        """

    @property
    def clean(self) -> cleanconfig.Clean:
        """What ``clean-container`` looks at and keeps.

        Returns:
            The ``[clean]`` table.
        """

    @property
    def args(self) -> argparse.Namespace:
        """The parsed arguments.

        Returns:
            The arguments.
        """

    @property
    def now(self) -> datetime.datetime:
        """The time of the run.

        Returns:
            The time.
        """


def require_ledger(path: pathlib.Path) -> None:
    """Exit 1 when the ledger file is absent: it is authoritative on the slots.

    Args:
        path: the ledger file.

    Raises:
        SystemExit: 1 when the file does not exist.
    """
    if not path.exists():
        print(
            f"LEDGER MISSING: {path} does not exist. It is authoritative on"
            " the slots and the owner creates it",
            file=sys.stderr,
        )
        raise SystemExit(1)

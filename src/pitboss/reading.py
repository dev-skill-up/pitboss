"""What a stage that reads GitHub needs of a command's context."""

import datetime
from typing import Protocol

from . import config, ghapi


class Reading(Protocol):
    """The part of a command's context that a stage reads with."""

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
    def now(self) -> datetime.datetime:
        """The time of the run.

        Returns:
            The time.
        """

"""What is offered to start: the queued work, less the owner's hold (keyword: pr-hold).

Shared by ``slots next``, ``next`` and the sweep, so the three agree on which
tickets are offered.
"""

import argparse
from typing import Protocol, Sequence

from . import config, configfile, ghapi, holds, ledger, pulls, shapes, work


class Source(Protocol):
    """The part of a command's context that the offer reads."""

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
    def args(self) -> argparse.Namespace:
        """The parsed arguments.

        Returns:
            The arguments.
        """


def _slug(each: pulls.Read) -> str:
    # an unreadable PR is open too, and its reference names its repository
    if isinstance(each, shapes.Unreadable):
        return each.reference.rpartition("#")[0]
    return each.repo.slug


def offered(
    found: Source, opened: Sequence[pulls.Read], book: ledger.Ledger
) -> work.Offered:
    """The work to start and the tickets the owner's hold keeps back.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger.

    Returns:
        The queued work, the held tickets apart.
    """
    owned = configfile.load_holds(
        found.args.config,
        configfile.working_directory(found.args),
        found.settings.project.repo.owner,
    )
    held = holds.standing(owned, [_slug(each) for each in opened])
    return work.apart(work.queued(opened, found.github, found.settings, book), held)

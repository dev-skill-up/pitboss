"""What to start next: the list, the empty slots and the briefs (keyword: brief).

Shared by ``slots next`` and ``next`` with no ticket (pitboss#118); it does not
import ``commands``, so the commands can import it.
"""

import argparse
import datetime
import itertools
import pathlib
import sys
from typing import Protocol, Sequence

from . import (
    briefconfig,
    config,
    ghapi,
    ledger,
    pulls,
    report,
    suggest,
    unreadableline,
    work,
)


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


def _view(
    found: Found, ordered: Sequence[work.Item], book: ledger.Ledger
) -> report.NextView:
    return report.NextView(
        items=ordered,
        assignments=work.assign(ordered, book, found.settings.slots),
        slots=found.settings.slots,
        failed=book.failed,
        now=found.now,
    )


def show(
    found: Found,
    opened: Sequence[pulls.Read],
    book: ledger.Ledger,
    project: briefconfig.Brief,
) -> None:
    """Print what to start next: the list, the empty slots and the briefs.

    Args:
        found: the context.
        opened: the open PRs, read or not.
        book: the slot ledger.
        project: what the project's briefs say beyond the process.
    """
    unreadableline.print_withheld(opened)
    ordered = work.queued(opened, found.github, found.settings, book)
    source = suggest.Source(
        github=found.github,
        settings=found.settings,
        given=found.args.config,
        brief=project,
        facts=pulls.readable(opened),
        items=ordered,
        failed=book.failed,
    )
    for line in itertools.chain(
        report.next_lines(_view(found, ordered, book)), suggest.lines(source)
    ):
        print(line)

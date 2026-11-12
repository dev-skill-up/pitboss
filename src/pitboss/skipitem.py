"""``slots next --skip ITEM``: an item the orchestrator skips (B2, keyword: skip-item).

The orchestrator read only the first ``NEXT`` line, a blocked PR it had to skip,
and the slot sat free while the list held startable items (owner, 2026-10-29 and
2026-11-11 20:25Z: a free slot is filled in the same turn, reading down the whole
list). ``--skip`` takes an item out of the list for this run, says so in a
``SKIPPED`` line, and the next item is the one the list starts.
"""

import argparse
import dataclasses
from typing import Sequence

from gather.commands import add_argument

from . import config, ledger, work

SKIP_ARGUMENT = add_argument(
    "--skip",
    action="append",
    default=[],
    metavar="ITEM",
    help="for 'slots next': leave this ticket or PR (owner/repo#N, repo#N or #N)"
    " out of the list and its briefs, say so in a SKIPPED line, and offer the next"
    " item in its place; repeatable",
)
SKIPPED = "SKIPPED: {reference} is left out of this list by --skip"


def named(args: argparse.Namespace, repo: config.Repo) -> Sequence[str]:
    """The items the command line skips.

    Args:
        args: the parsed arguments.
        repo: the project's repository, the owner of a bare ``#N``.

    Returns:
        Their references as ``owner/repo#N``, in the order given.
    """
    return [ledger.reference(each, repo) for each in getattr(args, "skip", ())]


def without(offer: work.Offered, skipped: Sequence[str]) -> work.Offered:
    """The offer less the skipped items.

    Args:
        offer: the queued work and the items kept back.
        skipped: the references to leave out.

    Returns:
        The offer whose items are the others, in the same order.
    """
    kept = [each for each in offer.items if each.reference not in skipped]
    return dataclasses.replace(offer, items=kept)


def lines(offer: work.Offered, skipped: Sequence[str]) -> Sequence[str]:
    """The ``SKIPPED`` line of each skipped item that the offer had.

    Args:
        offer: the queued work, before the skip.
        skipped: the references skipped.

    Returns:
        One line for each skipped item that was in the offer.
    """
    present = {each.reference for each in offer.items}
    return [SKIPPED.format(reference=each) for each in skipped if each in present]

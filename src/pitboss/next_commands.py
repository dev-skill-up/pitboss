"""The ``next`` command: the one step a ticket is at (keyword: review-flow)."""

import argparse
import re
import sys
from typing import AbstractSet, NoReturn, Sequence

from gather.commands import add_argument

from . import ENTRY_DATA, ledger, pulls, shapes, steps, tracefs, unreadableline
from .commands import CONFIG_ARGUMENT, NOW_ARGUMENT, load_context, open_pulls

_FULL_REFERENCE = re.compile(r"^[\w.-]+/[\w.-]+#\d+$")
_FIXES = re.compile(r"\bFixes\s+((?:[\w.-]+/)?[\w.-]*#\d+)(?!\w)", re.IGNORECASE)


def fixed_tickets(pull: pulls.PullFacts) -> AbstractSet[str]:
    """The tickets a PR's body says it fixes.

    Args:
        pull: the PR.

    Returns:
        Each ``Fixes #N`` or ``Fixes owner/repo#N`` of its body, in full.
    """
    return frozenset(
        ledger.reference(found, pull.repo) for found in _FIXES.findall(pull.pull.body)
    )


def fixing(
    found: Sequence[pulls.Read], ticket: str
) -> tuple[pulls.PullFacts | None, Sequence[shapes.Unreadable]]:
    """Pick the open PR that says it fixes a ticket.

    Args:
        found: the open PRs, read or not (read once for the run).
        ticket: the ticket, as ``owner/repo#N``.

    Returns:
        The first PR whose body says ``Fixes`` the ticket, or None, and the
        PRs that could not be read (one of them may be the ticket's).
    """
    named = (each for each in pulls.readable(found) if ticket in fixed_tickets(each))
    return next(named, None), pulls.failed_reads(found)


def _refuse(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _line(ticket: str, pull: pulls.PullFacts) -> str:
    step = pull.step
    return (
        f"{step.step.name}: {ticket} ({pulls.reference(pull)}): "
        f"{steps.describe(step)}"
    )


@ENTRY_DATA.register(CONFIG_ARGUMENT, add_argument("ticket"), NOW_ARGUMENT, name="next")
def show_next(args: argparse.Namespace) -> None:
    """Print the one step a ticket is at.

    TICKET is ``owner/repo#N``, ``repo#N`` or ``#N``. The open PRs are read
    once; the one whose body says ``Fixes`` the ticket is parsed, and its step
    is ``flow.next_step``. With no such PR the step is the ticket's first.

    Args:
        args: the parsed arguments.

    Raises:
        SystemExit: 1 when no PR names the ticket but a PR could not be read,
            so none is said not to exist.
    """
    tracefs.say(args.safe_run)
    found = load_context(args)
    ticket = ledger.reference(args.ticket, found.settings.project.repo)
    if not _FULL_REFERENCE.match(ticket):
        _refuse("next takes a ticket as owner/repo#N, repo#N or #N")
    pull, unread = fixing(open_pulls(found), ticket)
    if pull is not None:
        print(_line(ticket, pull))
        return
    for each in unread:
        print(unreadableline.unreadable_line(each))
    if unread:
        raise SystemExit(1)
    print(f"{steps.Step.WORKER.name}: {ticket}: {steps.FIRST_STEP}")

"""A worker's worktree is on its ticket's branch (B15, keyword: ticket-branch).

``nox`` and ``push`` given the ticket (``--ticket OWNER/REPO#N``, ``REPO#N``,
``#N`` or ``N``, or ``$PITBOSS_TICKET``) refuse a worktree whose current branch
does not name the ticket's number as a whole number (``worker/444``,
``pitboss-444``), so a worker never works or pushes in another ticket's worktree
or on the default branch. Without a ticket nothing is judged.
"""

import argparse
import os
import re
import subprocess
from typing import Mapping

from gather.commands import add_argument

TICKET_ARGUMENT = add_argument(
    "--ticket",
    default=None,
    help="the worker's ticket (OWNER/REPO#N, REPO#N, #N or N; default"
    " $PITBOSS_TICKET): the command refuses a worktree whose branch does not name"
    " the ticket's number, such as worker/444",
)
REFUSED = (
    "refused: branch {branch} does not name ticket {ticket}: work in your own"
    " worktree on the ticket's branch (git worktree add -b <branch-with-{number}>"
    " <path> origin/main)"
)
_NUMBER = re.compile(r"(\d+)$")


def number_of(ticket: str) -> str:
    """The number a ticket is spelled with.

    Args:
        ticket: ``OWNER/REPO#N``, ``REPO#N``, ``#N`` or ``N``.

    Returns:
        The digits at the end; empty when there are none.
    """
    found = _NUMBER.search(ticket.strip())
    return found.group(1) if found else ""


def names(branch: str, number: str) -> bool:
    """Whether a branch names a ticket's number as a whole number.

    Args:
        branch: the branch.
        number: the ticket's digits.

    Returns:
        True for ``worker/444`` and ``pitboss-444-fix`` and 444; not for
        ``worker/4440``, ``main`` or an empty (detached) branch.
    """
    return bool(number) and number in re.findall(r"\d+", branch)


def refusal(ticket: str, branch: str) -> str:
    """The refusal for a worktree on a branch that is not the ticket's.

    Args:
        ticket: the ticket as given.
        branch: the worktree's current branch, empty when detached.

    Returns:
        The line; empty when the branch names the ticket.
    """
    number = number_of(ticket)
    if names(branch, number):
        return ""
    return REFUSED.format(
        branch=branch or "(detached HEAD)", ticket=ticket, number=number or "N"
    )


def given(args: argparse.Namespace, env: Mapping[str, str]) -> str:
    """The ticket the command was given.

    Args:
        args: the parsed arguments.
        env: the environment.

    Returns:
        ``--ticket``, else ``$PITBOSS_TICKET``, else empty.
    """
    return getattr(args, "ticket", None) or env.get("PITBOSS_TICKET", "")


def require(args: argparse.Namespace, env: Mapping[str, str]) -> None:
    """Exit 1 when the worktree's branch is not the given ticket's.

    Args:
        args: the parsed arguments.
        env: the environment.

    Raises:
        SystemExit: 1 with the refusal printed.
    """
    ticket = given(args, env)
    if not ticket:
        return
    try:
        done = args.safe_run(["git", "branch", "--show-current"])
        branch = str(done.stdout).strip()
    except (OSError, subprocess.CalledProcessError):
        branch = ""
    said = refusal(ticket, branch)
    if said:
        print(said)
        raise SystemExit(1)


def enforce(args: argparse.Namespace) -> None:
    """Exit 1 when the worktree's branch is not the ticket's, by the environment.

    Args:
        args: the parsed arguments.
    """
    require(args, os.environ)

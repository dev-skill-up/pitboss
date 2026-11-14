"""A worker's worktree is on its ticket's branch (B15, keyword: ticket-branch).

``nox`` and ``push`` given the ticket (``--ticket OWNER/REPO#N``, ``REPO#N``,
``#N`` or ``N``, or ``$PITBOSS_TICKET``) refuse a worktree that is not on the
branch the ticket's PR is made for: the head branch of an open PR that works on
the ticket, read from GitHub for a ticket given as ``OWNER/REPO#N``; with no
such PR, a branch that names the ticket's number as a whole number
(``worker/444``, ``pitboss-444``). So a worker never works or pushes in another
ticket's worktree, on another PR's branch or on the default branch. Without a
ticket nothing is judged.
"""

import argparse
import os
import re
import subprocess
from typing import Mapping, Sequence

from gather.commands import add_argument

from . import config, ghapi, parsing, pullnames, running

TICKET_ARGUMENT = add_argument(
    "--ticket",
    default=None,
    help="the worker's ticket (OWNER/REPO#N, REPO#N, #N or N; default"
    " $PITBOSS_TICKET): the command refuses a worktree that is not on the head"
    " branch of the ticket's open PR, or, with none, on a branch that names the"
    " ticket's number, such as worker/444",
)
REFUSED = (
    "refused: branch {branch} does not name ticket {ticket}: work in your own"
    " worktree on the ticket's branch (git worktree add -b <branch-with-{number}>"
    " <path> origin/main)"
)
NOT_THE_PR = (
    "refused: branch {branch} is not the head branch of the PR of ticket {ticket}:"
    " work in a worktree on {heads}"
)
_NUMBER = re.compile(r"(\d+)$")
_FULL = re.compile(r"^([\w.-]+)/([\w.-]+)#(\d+)$")


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


def pull_branches(github: running.GitHub, ticket: str) -> Sequence[str]:
    """The head branches of the open PRs that work on a ticket.

    Args:
        github: the API.
        ticket: the ticket as given; only ``OWNER/REPO#N`` names a repository.

    Returns:
        Each branch; none for a ticket of no repository, or with no open PR.
    """
    found = _FULL.match(ticket.strip())
    if not found:
        return []
    repo = config.make_repo(found.group(1), found.group(2))
    path = f"repos/{repo.slug}/pulls?state=open"
    listed = parsing.pulls_of(ghapi.every(github, path))
    wanted = f"{repo.slug}#{found.group(3)}"
    return [
        each.head.branch
        for each in listed
        if wanted in pullnames.names(each.title, each.body, each.head.branch, repo)
    ]


def refusal(ticket: str, branch: str, heads: Sequence[str] = ()) -> str:
    """The refusal for a worktree on a branch that is not the ticket's.

    Args:
        ticket: the ticket as given.
        branch: the worktree's current branch, empty when detached.
        heads: the head branches of the ticket's open PRs (``pull_branches``).

    Returns:
        The line; empty when the branch is a head branch of the ticket's PR, or,
        with no PR, when it names the ticket.
    """
    if heads:
        if branch in heads:
            return ""
        shown = branch or "(detached HEAD)"
        return NOT_THE_PR.format(branch=shown, ticket=ticket, heads=", ".join(heads))
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
    heads = pull_branches(running.read_only(args.safe_run), ticket)
    said = refusal(ticket, branch, heads)
    if said:
        print(said)
        raise SystemExit(1)


def enforce(args: argparse.Namespace) -> None:
    """Exit 1 when the worktree's branch is not the ticket's, by the environment.

    Args:
        args: the parsed arguments.
    """
    require(args, os.environ)

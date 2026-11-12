"""What a worker says it pushed, read back from the PR on GitHub.

The keyword is claim-readback.

(quire#1115.) A conflict worker pushed to ``w1113-merge`` instead of the PR's branch
``w1113`` and reported the push: git's own read-back (``pushcheck``) compared the
remote ref with the local commit, which held, and nobody read the PR. Here the PR of
the worker's ticket is read after the push: its head branch must be the branch the
push went to (else ``WRONG-BRANCH``, naming both) and its head the commit pushed
(else ``push NOT LANDED``).
"""

import json
import subprocess
from typing import Sequence

from . import config, ghapi, parsing, pullnames, pushcheck, shapes, ticketbranch

WRONG_BRANCH = "WRONG-BRANCH"
NOT_LANDED = "push NOT LANDED"
_HEADS = "refs/heads/"


def ticket_pulls(
    github: ghapi.GitHub, repo: config.Repo, ticket: str
) -> Sequence[shapes.Pull]:
    """The open PRs of a repository that work on a ticket.

    Args:
        github: the API.
        repo: the repository.
        ticket: the ticket's number.

    Returns:
        The PRs whose title or body fixes the ticket, or whose branch ends in its
        number; none when the list cannot be read.
    """
    path = f"repos/{repo.slug}/pulls?state=open&per_page=100"
    try:
        listed = json.loads(ghapi.get(github, path))
    except (subprocess.CalledProcessError, ValueError):
        return []
    wanted = f"{repo.slug}#{ticket}"
    found = [parsing.pull(json.dumps(each)) for each in listed]
    return [
        each
        for each in found
        if wanted in pullnames.names(each.title, each.body, each.head.branch, repo)
    ]


def lines(
    pulls: Sequence[shapes.Pull], slug: str, ref: str, pushed: str
) -> Sequence[str]:
    """What the PRs of the ticket say of one pushed ref.

    Args:
        pulls: the open PRs of the worker's ticket.
        slug: the repository's ``owner/name``.
        ref: the full name of the ref pushed.
        pushed: the commit pushed to it.

    Returns:
        Nothing when the ticket has no PR yet (a first push) or the PR's head is the
        commit pushed to its branch; else a WRONG-BRANCH line when no PR has the
        pushed branch as its head branch, or a NOT LANDED line when the one that
        has it holds another commit.
    """
    branch = ref.removeprefix(_HEADS)
    if not pulls:
        return []
    same = [each for each in pulls if each.head.branch == branch]
    if not same:
        return [
            f"{WRONG_BRANCH} {slug}#{each.number}: pushed {pushed} to {branch}, but"
            f" the PR's head branch is {each.head.branch} (at {each.head.sha}): push"
            f" to {each.head.branch}, never to a branch of your own"
            for each in pulls
        ]
    return [
        f"{NOT_LANDED} {slug}#{each.number}: pushed {pushed} to {branch}, but the PR"
        f" head is {each.head.sha}"
        for each in same
        if each.head.sha != pushed
    ]


def read_back(
    github: ghapi.GitHub,
    repo: config.Repo,
    ticket: str,
    outcomes: Sequence[pushcheck.Outcome],
) -> Sequence[str]:
    """The lines about the PR of the ticket after a push that went out.

    Args:
        github: the API.
        repo: the repository pushed to.
        ticket: the worker's ticket; none is judged without one.
        outcomes: what the push came to, per ref.

    Returns:
        The WRONG-BRANCH and NOT LANDED lines of the refs the push moved.
    """
    moved = [
        each
        for each in outcomes
        if each.kind in (pushcheck.Kind.MOVED, pushcheck.Kind.ALREADY)
    ]
    number = ticketbranch.number_of(ticket)
    if not moved or not number:
        return []
    found = ticket_pulls(github, repo, number)
    return [
        said
        for each in moved
        for said in lines(found, repo.slug, each.target.ref, each.target.local)
    ]


def say(
    github: ghapi.GitHub,
    where: tuple[str | None, str],
    ticket: str,
    outcomes: Sequence[pushcheck.Outcome],
) -> None:
    """Print what ``read_back`` finds and exit 1 when it finds anything.

    Args:
        github: the API.
        where: the repository pushed to (``owner/name``, none when it cannot be
            told) and the owner a bare name belongs to.
        ticket: the worker's ticket.
        outcomes: what the push came to, per ref.

    Raises:
        SystemExit: 1 when the PR does not hold what was pushed.
    """
    slug, owner = where
    if slug is None:
        return
    said = read_back(github, config.parse_repo(slug, owner), ticket, outcomes)
    for line in said:
        print(line)
    if said:
        raise SystemExit(1)

"""What ``pitboss plan-check`` reads from GitHub (keywords: ci-run, plan-done-when).

The head of a run that a CI pointer names, and the ticket the body fixes, whose
Done-when the Plan copies (pitboss#317); the ticket's comments are never read
(pitboss#396). Each is one read of
``gh api``, none waits for anything. The readers return None, or a finding, for
what cannot be read: that is a finding of the Plan, not a crash.
"""

import json
import re
import subprocess
from typing import Sequence

from . import cirun, ghapi, plandigest, plandonewhen

ORIGIN = re.compile(r"github\.com[:/]([\w.-]+/[\w.-]+?)(?:\.git)?/?$")


def run_head(github: ghapi.GitHub) -> cirun.HeadOf:
    """A reader of the ``head_sha`` of a workflow run.

    Args:
        github: the API.

    Returns:
        Reads a run given its repository and id; None when it cannot be read.
    """

    def head_of(slug: str, run: int) -> str | None:
        try:
            found = json.loads(ghapi.get(github, f"repos/{slug}/actions/runs/{run}"))
        except (subprocess.CalledProcessError, OSError, ValueError):
            return None
        sha = found.get("head_sha") if isinstance(found, dict) else None
        return sha if isinstance(sha, str) else None

    return head_of


def slug_of(origin: str) -> str:
    """The ``owner/name`` of a GitHub remote's address.

    Args:
        origin: the address ``git remote get-url`` printed.

    Returns:
        The slug; empty when the address is not a GitHub repository's.
    """
    found = ORIGIN.search(origin.strip())
    return found.group(1) if found else ""


def done_when(
    github: ghapi.GitHub, ticket: str, repository: str, body: str
) -> Sequence[str]:
    """The findings for a Plan whose Done-when is not the fixed ticket's.

    Args:
        github: the API.
        ticket: the ticket the PR's first ``Fixes`` line names (``#7`` or
            ``owner/name#7``); empty when it fixes none.
        repository: the ``owner/name`` that owns a bare ``#N``.
        body: the PR's body.

    Returns:
        The findings of ``plandonewhen.findings`` and ``plandonewhen.edited``,
        or one that says why the ticket cannot be read; none when the PR fixes
        no ticket. Only the ticket's body is read, never its comments
        (pitboss#396).
    """
    if not ticket:
        return []
    slug, _, number = ticket.rpartition("#")
    slug = slug or repository
    if not slug:
        return [f"{plandonewhen.CHECK}: {ticket} names no repository"]
    return _of_ticket(github, f"{slug}#{number}", body)


def _of_ticket(github: ghapi.GitHub, ticket: str, body: str) -> Sequence[str]:
    # the findings of one ticket read from its body alone
    text = body_of(github, ticket)
    if text is None:
        return [f"{plandonewhen.CHECK}: the ticket {ticket} cannot be read"]
    return [
        *plandonewhen.findings(plandigest.section(body), text),
        *plandonewhen.edited(body, text),
    ]


def issue_path(ticket: str) -> str:
    """The API path of a ticket.

    Args:
        ticket: the ticket as ``owner/name#N``.

    Returns:
        ``repos/owner/name/issues/N``.
    """
    return "repos/" + ticket.replace("#", "/issues/")


def body_of(github: ghapi.GitHub, ticket: str) -> str | None:
    """The body of a ticket.

    Args:
        github: the API.
        ticket: the ticket as ``owner/name#N``.

    Returns:
        Its body, empty when it has none; None when GitHub does not give it.
    """
    try:
        return str(json.loads(ghapi.get(github, issue_path(ticket))).get("body") or "")
    except (subprocess.CalledProcessError, OSError, ValueError, AttributeError):
        return None

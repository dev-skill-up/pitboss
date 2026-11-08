"""What ``pitboss plan-check`` reads from GitHub (keywords: ci-run, plan-done-when).

The head of a run that a CI pointer names, and the ticket the body fixes with its
comments, whose Done-when the Plan copies (pitboss#317). Each is one read of
``gh api``, none waits for anything. The readers return None, or a finding, for
what cannot be read: that is a finding of the Plan, not a crash.
"""

import json
import re
import subprocess
from typing import Sequence

from . import cirun, ghapi, ghstore, plandonewhen

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
    github: ghapi.GitHub, ticket: str, repository: str, section: str
) -> Sequence[str]:
    """The findings for a Plan whose Done-when is not the fixed ticket's.

    Args:
        github: the API.
        ticket: the ticket the PR's first ``Fixes`` line names (``#7`` or
            ``owner/name#7``); empty when it fixes none.
        repository: the ``owner/name`` that owns a bare ``#N``.
        section: the Plan section.

    Returns:
        The findings of ``plandonewhen.findings``, or one that says why the
        ticket cannot be read; none when the PR fixes no ticket.
    """
    if not ticket:
        return []
    slug, _, number = ticket.rpartition("#")
    slug = slug or repository
    if not slug:
        return [f"{plandonewhen.CHECK}: {ticket} names no repository"]
    path = f"repos/{slug}/issues/{number}"
    try:
        found = json.loads(ghapi.get(github, path))
        listed = ghapi.pages(github, f"{path}/comments", ghstore.listed)
    except (subprocess.CalledProcessError, OSError, ValueError):
        return [f"{plandonewhen.CHECK}: the ticket {slug}#{number} cannot be read"]
    comments = [each.body for each in listed]
    return plandonewhen.findings(section, str(found.get("body") or ""), comments)

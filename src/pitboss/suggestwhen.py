"""The subject of a brief, with the digest of its ticket's Done-when (pitboss#396).

A brief for a new PR prints the digest of the ticket's Done-when as it is now,
and the worker keeps it in the PR body (``Done-when digest:``); ``pitboss
plan-check`` compares it with the ticket's, which is how a Done-when edited
after a worker started is found (keyword: plan-done-when). Only the briefs that
open the body print it. The ticket is read from its body alone.
"""

import json
import subprocess

from . import brief, ghapi, ticketwhen

BODY_WRITERS = frozenset({brief.Kind.NEW_PR, brief.Kind.FIRST_ROUND})


def digest(github: ghapi.GitHub, ticket: str) -> str:
    """The digest of a ticket's Done-when now.

    Args:
        github: the API.
        ticket: the ticket as ``owner/name#N``; empty when none is known.

    Returns:
        The digest of ``ticketwhen.digest``; empty when there is no ticket, it
        cannot be read, or it has no Done-when.
    """
    slug, _, number = ticket.rpartition("#")
    if not slug:
        return ""
    try:
        found = json.loads(ghapi.get(github, f"repos/{slug}/issues/{number}"))
    except (subprocess.CalledProcessError, OSError, ValueError):
        return ""
    body = found.get("body") if isinstance(found, dict) else None
    return ticketwhen.digest(body) if isinstance(body, str) else ""


def subject(
    github: ghapi.GitHub, reference: str, ticket: str, goal: str, kind: brief.Kind
) -> brief.Subject:
    """What a brief is about.

    Args:
        github: the API.
        reference: the PR, or the ticket of a new PR, as ``owner/name#N``.
        ticket: the ticket the PR fixes, empty when its body names none.
        goal: the ticket's original goal in one line.
        kind: the kind of brief.

    Returns:
        The subject; it has the Done-when digest only for a brief that opens
        the PR's body.
    """
    return brief.Subject(
        reference=reference,
        ticket=ticket,
        repo=reference.rpartition("#")[0],
        goal=goal,
        done_when_digest=digest(github, ticket) if kind in BODY_WRITERS else "",
    )

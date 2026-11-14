"""A p0 test ticket's briefs add the project's lines (keyword: flake, pitboss#278)."""

import dataclasses

from . import brief, flake, ghapi, ticketread


def is_flake(github: ghapi.GitHub, ticket: str) -> bool:
    """Whether a ticket is a p0 about a failing test (keyword: flake).

    Args:
        github: the API.
        ticket: the ticket as ``owner/name#N``; empty when none is known.

    Returns:
        True when it can be read and ``flake.is_flake`` holds.
    """
    found = ticketread.issue(github, ticket) if ticket.rpartition("#")[0] else None
    return flake.issue_is_flake(found)


def rules_of(github: ghapi.GitHub, ticket: str, rules: brief.Rules) -> brief.Rules:
    """The rules, with the project's flake lines first when the ticket is one.

    Args:
        github: the API.
        ticket: the ticket as ``owner/name#N``; empty when none is known.
        rules: the project's rules; the ticket is read only when they list
            flake lines.

    Returns:
        The rules, their worker and review lines led by the flake lines.
    """
    project = rules.project
    if not (project.flake_worker_lines or project.flake_review_lines):
        return rules
    if not is_flake(github, ticket):
        return rules
    led = dataclasses.replace(
        project,
        worker_lines=(*project.flake_worker_lines, *project.worker_lines),
        review_lines=(*project.flake_review_lines, *project.review_lines),
    )
    return dataclasses.replace(rules, project=led)

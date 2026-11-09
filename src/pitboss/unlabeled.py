"""The tickets with no priority label, printed first (pitboss#94).

The work order is strict only when every ticket has a priority label: a ticket
with none has nothing to sort by. ``slots next``, ``next`` and the sweep print a
``NO PRIORITY LABEL`` line for each such ticket of every repository of the
configuration, then the rule, before the order itself. A ticket has a priority
label when it carries one of the configured ones or any ``pN`` (``p3`` is never
offered, but it is a priority).
"""

import re
from typing import Sequence

from . import concurrently, config, ghapi, issuepages, shapes

NO_LABEL = "NO PRIORITY LABEL"
RULE = (
    "RULE: label each ticket above by the criteria (p0, p1, p2 or p3), then the"
    " order below is strict: open pull requests oldest first, then tickets by"
    " priority label, oldest first"
)
_PRIORITY = re.compile(r"^p\d+$")


def _has_priority(issue: shapes.Issue, settings: config.Config) -> bool:
    known = settings.slots.priority_labels
    return any(label in known or _PRIORITY.match(label) for label in issue.labels)


def references(github: ghapi.GitHub, settings: config.Config) -> Sequence[str]:
    """The open tickets with no priority label, oldest first.

    Args:
        github: the API.
        settings: the configuration; with no priority labels configured nothing
            is unlabeled.

    Returns:
        Each ticket as ``owner/name#number``, across every repository of the
        configuration, oldest first by creation time.
    """
    if not settings.slots.priority_labels:
        return []
    repos = config.repositories(settings)

    def read(repo: config.Repo) -> Sequence[shapes.Issue]:
        path = f"repos/{repo.slug}/issues?state=open"
        # the list holds PRs: a full page with one among it is not the last page
        return list(filter(None, ghapi.pages(github, path, issuepages.entries)))

    found = [
        (each.created_at, f"{repo.slug}#{each.number}")
        for repo, opened in zip(repos, concurrently.each(read, repos))
        for each in opened
        if not _has_priority(each, settings)
    ]
    return [reference for _, reference in sorted(found)]


def lines(github: ghapi.GitHub, settings: config.Config) -> Sequence[str]:
    """The ``NO PRIORITY LABEL`` lines and, after them, the rule.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        A line for each unlabeled ticket then the rule's line; none when every
        ticket has a priority label.
    """
    found = references(github, settings)
    if not found:
        return []
    return [*(f"{NO_LABEL} {each}" for each in found), RULE]


def print_lines(github: ghapi.GitHub, settings: config.Config) -> None:
    """Print the ``NO PRIORITY LABEL`` lines and the rule.

    Args:
        github: the API.
        settings: the configuration.
    """
    found = lines(github, settings)
    if found:
        print("\n".join(found))

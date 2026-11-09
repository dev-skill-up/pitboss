"""The open tickets of every repository, counted by priority (keyword: ticket-count).

The orchestrator's answer to "how many p0 are left" is this count over the whole
configuration, not a search of some repositories (pitboss#281).
"""

import dataclasses
import re
from typing import Collection, Sequence

from . import concurrently, config, ghapi, issuelist

PRIORITIES = ("p0", "p1", "p2", "p3")
UNLABELLED = "unlabelled"
SHOWN = (*PRIORITIES, UNLABELLED)
_PRIORITY = re.compile(r"^p\d+$")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Counted:
    """An open ticket and the priority it is counted at.

    Attributes:
        repo: its repository's ``owner/name``.
        number: its number.
        title: its title.
        priority: ``p0`` to ``p3``, its highest label of those, else ``unlabelled``.
    """

    repo: str
    number: int
    title: str
    priority: str


def priority_of(labels: Collection[str]) -> str:
    """The priority a ticket is counted at.

    Args:
        labels: the ticket's labels.

    Returns:
        The highest of ``p0`` to ``p3`` it carries; ``unlabelled`` when it carries
        none (any other ``pN`` is no priority of this count).
    """
    return next((each for each in PRIORITIES if each in labels), UNLABELLED)


def _tickets(github: ghapi.GitHub, repo: config.Repo) -> Sequence[Counted]:
    path = f"repos/{repo.slug}/issues?state=open"
    issues = filter(None, ghapi.pages(github, path, issuelist.listed))
    return [
        Counted(
            repo=repo.slug,
            number=issue.number,
            title=issue.title,
            priority=priority_of(issue.labels),
        )
        for issue in sorted(issues, key=lambda issue: issue.number)
    ]


def read(github: ghapi.GitHub, repos: Sequence[config.Repo]) -> Sequence[Counted]:
    """Read the open tickets of the repositories, PRs left out.

    Args:
        github: the API.
        repos: the repositories.

    Returns:
        Every open ticket, by repository then number.
    """

    def opened(repo: config.Repo) -> Sequence[Counted]:
        return _tickets(github, repo)

    return [each for found in concurrently.each(opened, repos) for each in found]


def render(
    slugs: Sequence[str], found: Sequence[Counted], shown: Sequence[str]
) -> Sequence[str]:
    """The lines of the count.

    For each priority shown: a line for each repository (one with none too), the
    total line, and the tickets.

    Args:
        slugs: every repository counted, in order.
        found: the open tickets.
        shown: the priorities to print.

    Returns:
        The lines.
    """
    lines: list[str] = []
    for priority in shown:
        at = [each for each in found if each.priority == priority]
        lines.append(priority)
        lines.extend(
            f"  {slug}: {sum(each.repo == slug for each in at)}" for slug in slugs
        )
        lines.append(f"  total: {len(at)}")
        lines.extend(f"  {each.repo}#{each.number} {each.title}" for each in at)
    return lines

"""The open p0 tickets, and which red runs of the window each cites."""

import dataclasses
import enum
import re
from typing import AbstractSet, Sequence

from . import config, ghapi, parsing, shapes
from .redtime import seconds


class Label(enum.Enum):
    """The labels the analysis reads.

    Attributes:
        PRIORITY: the highest priority; its open issues are listed.
        QUARANTINED: the test of the issue is quarantined.
    """

    PRIORITY = enum.auto()
    QUARANTINED = enum.auto()


LABEL_NAMES = {Label.PRIORITY: "p0", Label.QUARANTINED: "quarantined"}
DAY_SECONDS = 24 * 3600


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """An open p0 issue.

    Attributes:
        repo: its repository's ``owner/name``.
        number: its number.
        title: its title.
        created_at: when it was opened (ISO 8601).
        labels: its labels.
        cited: the window's red run ids its text or comments name.
        first_citation: when it first named one (ISO 8601), else empty.
    """

    repo: str
    number: int
    title: str
    created_at: str
    labels: AbstractSet[str]
    cited: Sequence[int]
    first_citation: str


def name(ticket: Ticket) -> str:
    """The ticket's short name.

    Args:
        ticket: the ticket.

    Returns:
        ``owner/repo#number``.
    """
    return f"{ticket.repo}#{ticket.number}"


def url(ticket: Ticket) -> str:
    """The ticket's page.

    Args:
        ticket: the ticket.

    Returns:
        Its URL.
    """
    return f"https://github.com/{ticket.repo}/issues/{ticket.number}"


def _names(text: str, run: int) -> bool:
    return re.search(rf"(?<!\d){run}(?!\d)", text) is not None


def _read(
    github: ghapi.GitHub, repo: config.Repo, issue: shapes.Issue, runs: Sequence[int]
) -> Ticket:
    path = f"repos/{repo.slug}/issues/{issue.number}/comments"
    comments = ghapi.pages(github, path, parsing.comments)
    texts = [(issue.created_at, issue.body)] + [
        (each.created_at, each.body) for each in comments
    ]
    cited = [run for run in runs if any(_names(text, run) for _, text in texts)]
    times = [when for when, text in texts if any(_names(text, run) for run in cited)]
    return Ticket(
        repo=repo.slug,
        number=issue.number,
        title=issue.title,
        created_at=issue.created_at,
        labels=issue.labels,
        cited=cited,
        first_citation=min(times) if times else "",
    )


def read_tickets(
    github: ghapi.GitHub, repos: Sequence[config.Repo], runs: Sequence[int]
) -> Sequence[Ticket]:
    """Read the open p0 issues of the repositories.

    Args:
        github: the API.
        repos: the repositories.
        runs: the window's red run ids.

    Returns:
        The tickets, with the runs each cites.
    """
    found = []
    for each in repos:
        path = (
            f"repos/{each.slug}/issues?state=open&labels={LABEL_NAMES[Label.PRIORITY]}"
        )
        for issue in ghapi.pages(github, path, parsing.issues):
            found.append(_read(github, each, issue, runs))
    return found


def age_seconds(ticket: Ticket) -> int | None:
    """Seconds from a ticket's opening to its first citation of a red.

    Args:
        ticket: the ticket.

    Returns:
        The age, or ``None`` when it cites no red run.
    """
    if not ticket.first_citation:
        return None
    return seconds(ticket.created_at, ticket.first_citation)


def open_a_day_after(ticket: Ticket, now: str) -> bool:
    """Whether a red cited the ticket and it is still open a day later.

    Args:
        ticket: the (open) ticket.
        now: the time now (ISO 8601).

    Returns:
        True when it cites a red run and a day has passed since.
    """
    if not ticket.first_citation:
        return False
    return seconds(ticket.first_citation, now) >= DAY_SECONDS

"""The open tickets that block a PR, named by a status or a label (pitboss#162).

A failed status or a label of a PR can name the ticket that causes it
(``text-lint`` failing on every PR of a repository because of a stale pin that
a ticket moves). Each name is resolved with one API call and only an open ticket
is shown, with its link (keyword: red-status).

A ticket also says what it cannot be worked on until (``ticketblock``): the open
blockers of a ticket, and of the ticket a PR fixes, are read here too (keyword:
ticket-blocked, blocked-pull, pitboss#388).
"""

import dataclasses
import json
import re
import functools
from typing import AbstractSet, Iterable, Mapping, Protocol, Sequence

from . import (
    config,
    ghapi,
    ledger,
    planrefusal,
    pulls,
    supersedes,
    ticketblock,
    ticketread,
)

NAME = re.compile(r"(?:[\w.-]+/)?[\w.-]*#\d+")
URL = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)")
LINK = "https://github.com/{slug}/issues/{number}"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Ticket:
    """A ticket as ``issues/<number>`` gives it.

    Attributes:
        open: whether it is open.
        labels: its labels' names.
        body: its text (keyword: done-when-names).
        title: its title.
        created_at: when it was opened (ISO 8601).
        comments: how many comments it has.
        pull: whether it is a PR (``issues/<number>`` answers for both).
    """

    open: bool
    labels: AbstractSet[str]
    body: str = ""
    title: str = ""
    created_at: str = ""
    comments: int = 0
    pull: bool = False


def named(text: str, repo: config.Repo) -> Iterable[str]:
    """The tickets a text names, as ``owner/name#number``.

    Args:
        text: a status description or a label.
        repo: the repository of a bare ``#12``.

    Returns:
        The references, in the order of the text.
    """
    return [
        *(ledger.reference(found, repo) for found in NAME.findall(text)),
        *(f"{slug}#{number}" for slug, number in URL.findall(text)),
    ]


def read(github: ghapi.GitHub, reference: str) -> Ticket | None:
    """Read a ticket.

    Args:
        github: the API.
        reference: ``owner/name#number``.

    Returns:
        The ticket, or None when the API cannot give it.
    """
    text = ticketread.text(github, reference)
    if text is None:
        return None
    item = json.loads(text)
    listed = item.get("labels", ())
    return Ticket(
        open=item["state"] == "open",
        labels=frozenset(str(label["name"]) for label in listed),
        body=item.get("body") or "",
        title=item.get("title") or "",
        created_at=item.get("created_at") or "",
        comments=int(item.get("comments") or 0),
        pull="pull_request" in item,
    )


def open_ticket(github: ghapi.GitHub, reference: str) -> Ticket | None:
    """Read a ticket that is open.

    Args:
        github: the API.
        reference: ``owner/name#number``.

    Returns:
        The ticket, or None when it is closed, merged or cannot be read.
    """
    ticket = read(github, reference)
    return ticket if ticket is not None and ticket.open else None


def candidates(
    github: ghapi.GitHub,
    pull: pulls.PullFacts,
    fixed: AbstractSet[str],
    description: str,
) -> Mapping[str, str]:
    """Every ticket the description, the PR's labels or its tickets' labels name.

    Args:
        github: the API.
        pull: the PR.
        fixed: the tickets the PR's body says it fixes.
        description: the failed status's description.

    Returns:
        Each reference with where it was named.
    """
    repo = pull.repo
    found = {each: "the status description" for each in named(description, repo)}
    for label in sorted(pull.signals.labels):
        for each in named(label, repo):
            found.setdefault(each, f"the label {label} of the PR")
    for each_fixed in sorted(fixed):
        ticket = read(github, each_fixed)
        for label in sorted(ticket.labels if ticket else ()):
            for each in named(label, repo):
                found.setdefault(each, f"the label {label} of {each_fixed}")
    return found


def lines(
    github: ghapi.GitHub,
    pull: pulls.PullFacts,
    fixed: AbstractSet[str],
    description: str,
) -> Sequence[str]:
    """The open tickets that block a PR, each with its link and where it was named.

    Args:
        github: the API.
        pull: the PR.
        fixed: the tickets the PR's body says it fixes.
        description: the failed status's description.

    Returns:
        One text for each open ticket; a closed or unreadable one is left out.
    """
    shown = []
    for reference, where in candidates(github, pull, fixed, description).items():
        ticket = read(github, reference)
        if ticket is not None and ticket.open:
            slug, _, number = reference.rpartition("#")
            link = LINK.format(slug=slug, number=number)
            shown.append(f"blocked by the open ticket {link} (named by {where})")
    return shown


def _is_open(github: ghapi.GitHub, reference: str) -> bool:
    return open_ticket(github, reference) is not None


def open_blockers(
    github: ghapi.GitHub,
    reference: str,
    texts: Sequence[str],
    own: AbstractSet[str] = frozenset(),
) -> Sequence[str]:
    """The open tickets and PRs the texts of a ticket say it waits for.

    Args:
        github: the API.
        reference: the ticket, ``owner/name#number``.
        texts: its body, then its trusted comments, oldest first.
        own: references that never block it (the PR that fixes it).

    Returns:
        The blockers that are open, each once.
    """
    return ticketblock.open_blockers(
        config.repo_of(reference),
        texts,
        functools.partial(_is_open, github),
        own | {reference},
    )


class Described(Protocol):
    """A ticket as read: its text and how many comments it has."""

    @property
    def body(self) -> str:
        """The ticket's text.

        Returns:
            The body.
        """

    @property
    def comments(self) -> int:
        """How many comments the ticket has.

        Returns:
            The count.
        """


def _texts(
    github: ghapi.GitHub, settings: config.Config, ticket: Described, reference: str
) -> Sequence[str]:
    # the body, then the trusted comments; none are read for a ticket with none
    if not ticket.comments:
        return [ticket.body]
    trusted = settings.review.trusted
    return [ticket.body, *ticketblock.comments_of(github, reference, trusted)]


def waiting(
    github: ghapi.GitHub, settings: config.Config, ticket: Described, reference: str
) -> tuple[Sequence[str], bool]:
    """What a ticket says it cannot be worked on until, and whether it is superseded.

    The body and the trusted comments are read for ``Cannot be worked on until
    <owner/repo#n>``, ``Blocked by <owner/repo#n>`` or ``Depends on
    <owner/repo#n>``; a blocker that is closed or merged blocks nothing. A
    tracking ticket whose newest comment says it ``closes when #a and #b have
    merged`` is blocked by each of them that is open (keyword: closes-when). A
    ticket the configuration or a comment line marks is superseded (keyword:
    superseded-ticket).

    Args:
        github: the API.
        settings: the configuration.
        ticket: the ticket as read.
        reference: its ``owner/name#number``.

    Returns:
        The open blockers, and whether the ticket is superseded.
    """
    texts = _texts(github, settings, ticket, reference)
    gone = reference in settings.slots.superseded or supersedes.marked(texts[1:])
    return open_blockers(github, reference, texts), gone


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Waits:
    """What a PR waits for because its ticket does, and how it ranks then.

    Attributes:
        blockers: the open tickets and PRs the ticket waits for.
        created_at: when the ticket was opened.
        priority: the index of the ticket's priority label.
    """

    blockers: Sequence[str]
    created_at: str
    priority: int


def _rank(settings: config.Config, labels: AbstractSet[str]) -> int:
    # the highest priority label a ticket has, else the lowest priority
    ranked = settings.slots.priority_labels
    having = [at for at, label in enumerate(ranked) if label in labels]
    return min(having, default=max(len(ranked) - 1, 0))


def pull_waits(
    github: ghapi.GitHub, settings: config.Config, pull: str, ticket: str
) -> Waits | None:
    """What the ticket a PR fixes waits for (keyword: blocked-pull, pitboss#388).

    Args:
        github: the API.
        settings: the configuration.
        pull: the PR, which never blocks its own ticket.
        ticket: the ticket it fixes.

    Returns:
        What it waits for, or None when the ticket is closed or cannot be read.
    """
    found = open_ticket(github, ticket)
    if found is None:
        return None
    texts = _texts(github, settings, found, ticket)
    return Waits(
        blockers=open_blockers(github, ticket, texts, {pull}),
        created_at=found.created_at,
        priority=_rank(settings, found.labels),
    )


def refusal_blockers(
    github: ghapi.GitHub, settings: config.Config, pull: str, ticket: str
) -> Sequence[str]:
    """The open tickets and PRs that the refused Plan check of a PR names.

    Args:
        github: the API.
        settings: the configuration.
        pull: the PR, ``owner/name#number``, which never blocks itself.
        ticket: the ticket it fixes, which never blocks it either.

    Returns:
        The references, each once, in the order of the newest trusted ``Plan
        check`` comment, when that comment refuses the Plan (keyword:
        plan-refusal, pitboss#388).
    """
    trusted = settings.review.trusted
    text = planrefusal.refusing(ticketblock.comments_of(github, pull, trusted))
    names = named(text, config.repo_of(pull)) if text else []
    wanted = dict.fromkeys(each for each in names if each not in {pull, ticket})
    return [each for each in wanted if _is_open(github, each)]

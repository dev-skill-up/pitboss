"""The open tickets that block a PR, named by a status or a label (pitboss#162).

A failed status or a label of a PR can name the ticket that causes it
(``text-lint`` failing on every PR of a repository because of a stale pin that
a ticket moves). Each name is resolved with one API call and only an open ticket
is shown, with its link (keyword: red-status).
"""

import dataclasses
import json
import re
import subprocess
from typing import AbstractSet, Iterable, Mapping, Sequence

from . import config, ghapi, ledger, pulls

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
    slug, _, number = reference.rpartition("#")
    try:
        text = ghapi.get(github, f"repos/{slug}/issues/{number}")
    except subprocess.CalledProcessError:
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

"""What keeps one ticket back, read from that ticket and its repository alone.

A ticket is offered when no open PR names it, it has a priority, and a hold, a
blocker or a supersession does not keep it back. Each of those is read from the
ticket, its repository's open PRs, its timeline (a PR of another repository that
names it) and the tickets its text names, so no call lists the issues or PRs of
another repository (keyword: item-brief, pitboss#443).
"""

import json
from typing import AbstractSet, Callable, Sequence

from . import blockers, config, ghapi, nextfound, pullnames

Found = nextfound.Found


class Unknown(Exception):
    """The item is not offered; the message says what keeps it back."""


class Whole(Exception):
    """Only the whole order can tell."""


def _named(repo: config.Repo) -> Callable[[str], Sequence[frozenset[str]]]:
    # the tickets each raw PR of the list names (a short page is the last one)
    def parse(text: str) -> Sequence[frozenset[str]]:
        return [
            frozenset(
                pullnames.names(
                    each.get("title") or "",
                    each.get("body") or "",
                    each["head"]["ref"],
                    repo,
                )
            )
            for each in json.loads(text)
        ]

    return parse


def _crossed(text: str) -> Sequence[bool]:
    # whether each event is a mention by a PR that is open
    return [
        each.get("event") == "cross-referenced"
        and "pull_request" in each["source"]["issue"]
        and each["source"]["issue"]["state"] == "open"
        for each in json.loads(text)
    ]


def taken(found: Found, repo: config.Repo, reference: str) -> tuple[int, bool]:
    """How many PRs the repository has open, and whether one names the ticket.

    Args:
        found: the context.
        repo: the ticket's repository.
        reference: the ticket as ``owner/repo#N``.

    Returns:
        The count of open PRs of the repository, and whether a PR of any
        repository (its timeline) names the ticket.
    """
    github = found.github
    opened = ghapi.pages(github, f"repos/{repo.slug}/pulls?state=open", _named(repo))
    path = f"repos/{repo.slug}/issues/{reference.rpartition('#')[2]}/timeline"
    mentions = ghapi.pages(github, path, _crossed)
    return len(opened), any(reference in each for each in opened) or any(mentions)


def priority(settings: config.Config, reference: str, labels: AbstractSet[str]) -> int:
    """The index of the priority label a ticket ranks by.

    Args:
        settings: the configuration.
        reference: the ticket as ``owner/repo#N``.
        labels: the ticket's labels.

    Returns:
        The owner's stated rank, else the first priority label it has.

    Raises:
        Whole: when it has none, since it may still be offered as the
            dependency of another ticket.
    """
    ranked = settings.slots.priority_labels
    stated = settings.slots.owner_priorities.get(reference)
    having = [at for at, label in enumerate(ranked) if label in labels]
    if stated is not None:
        return ranked.index(stated)
    if not having:
        raise Whole
    return min(having)


def kept_back(found: Found, reference: str, ticket: blockers.Ticket) -> None:
    """Say what the text of a ticket keeps it back for.

    Args:
        found: the context.
        reference: the ticket as ``owner/repo#N``.
        ticket: the ticket.

    Raises:
        Unknown: for a blocker or a supersession the ticket's text says.
    """
    waits, gone = blockers.waiting(found.github, found.settings, ticket, reference)
    if gone:
        raise Unknown("it is superseded")
    if waits:
        raise Unknown(f"it waits for {', '.join(waits)}")

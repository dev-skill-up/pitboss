"""What keeps one ticket back, read from that ticket and its repository alone.

A ticket is offered when no open PR names it, it has a priority, and a hold, a
blocker or a supersession does not keep it back. Each of those is read from the
ticket, its repository's open PRs, its timeline (a PR of another repository that
names it) and the tickets its text names, so no call lists the issues or PRs of
another repository (keyword: item-brief, pitboss#443).
"""

import json
from typing import AbstractSet, Callable, Mapping, Sequence

from . import blockers, config, ghapi, nextfound, pullnames

Found = nextfound.Found


class Unknown(Exception):
    """The item is not offered; the message says what keeps it back."""


class Whole(Exception):
    """Only the whole order can tell."""


Listed = tuple[int, frozenset[str]]


def _named(repo: config.Repo) -> Callable[[str], Sequence[Listed]]:
    # each raw PR of the list: its number and the tickets it names (a short page
    # is the last one)
    def parse(text: str) -> Sequence[Listed]:
        raws = json.loads(text)
        tickets = [
            pullnames.names(
                each.get("title") or "",
                each.get("body") or "",
                each["head"]["ref"],
                repo,
            )
            for each in raws
        ]
        return [(each.get("number", 0), frozenset(t)) for each, t in zip(raws, tickets)]

    return parse


def _crossed(reference: str, repo: config.Repo) -> Callable[[str], Sequence[str]]:
    # the open PR that fixes the ticket when an event is its mention, else "" (a
    # mention in a Plan or an Evidence block does not, keyword: taken, pitboss#448)
    def parse(text: str) -> Sequence[str]:
        return [
            (
                f"#{each['source']['issue'].get('number')}"
                if each.get("event") == "cross-referenced"
                and _fixing(each["source"]["issue"], reference, repo)
                else ""
            )
            for each in json.loads(text)
        ]

    return parse


def _fixing(issue: Mapping[str, object], reference: str, repo: config.Repo) -> bool:
    # an open PR, of the repository the issue names, that fixes the ticket
    if "pull_request" not in issue or issue.get("state") != "open":
        return False
    home = f"{issue.get('repository_url')}".rpartition("repos/")[2]
    owner = config.make_repo(*home.split("/", 1)) if "/" in home else repo
    named = pullnames.names(f"{issue.get('title')}", f"{issue.get('body')}", "", owner)
    return reference in named


def taken(found: Found, repo: config.Repo, reference: str) -> tuple[int, str]:
    """How many PRs the repository has open, and whether one names the ticket.

    Args:
        found: the context.
        repo: the ticket's repository.
        reference: the ticket as ``owner/repo#N``.

    Returns:
        The count of open PRs of the repository, and what names the ticket: the
        PRs of the repository that do (``PR owner/name#N names it``) and the PRs
        of its timeline (``the timeline shows PR #N``) with the rule; empty when
        none does (D1, keyword: unknown-data).
    """
    github = found.github
    opened = ghapi.pages(github, f"repos/{repo.slug}/pulls?state=open", _named(repo))
    path = f"repos/{repo.slug}/issues/{reference.rpartition('#')[2]}/timeline"
    mentions = ghapi.pages(github, path, _crossed(reference, repo))
    return len(opened), _why(repo, reference, opened, mentions)


def _why(
    repo: config.Repo,
    reference: str,
    opened: Sequence[Listed],
    mentions: Sequence[str],
) -> str:
    # what names the ticket, with the rule (D1, keyword: unknown-data)
    by_title = [
        f"PR {repo.slug}#{number} names it in its title, body or branch"
        for number, names in opened
        if reference in names
    ]
    by_timeline = [
        f"the timeline of the ticket shows the open PR {each} fixing it"
        for each in mentions
        if each
    ]
    return "; ".join([*by_title, *by_timeline])


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

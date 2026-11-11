"""The oldest tickets of each priority, read page by page as far as needed.

``slots next`` needs the top of the order, which is the PRs and then the tickets
by priority label and age. GitHub lists a label's issues oldest first
(``sort=created&direction=asc``), so the first page of each repository holds
that repository's oldest tickets, and the merge of the repositories' lists by
age gives the oldest tickets of all without reading the rest. A page after the
first is read only when the merge has used up the one before it (keyword:
ticket-window, pitboss#443).
"""

import dataclasses
import heapq
from typing import AbstractSet, Iterator, Sequence

from . import concurrently, config, ghapi, issuelist, shapes

Page = Sequence[shapes.Issue | None]
Tagged = tuple[str, shapes.Issue]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Asked:
    """Which tickets are wanted.

    Attributes:
        repos: the repositories.
        labels: the priority labels, highest first.
        skip: tickets that are left out (an open PR works on them).
    """

    repos: Sequence[config.Repo]
    labels: Sequence[str]
    skip: AbstractSet[str]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Found:
    """A ticket of the window.

    Attributes:
        priority: the index of the label it was found under.
        reference: its ``owner/name#number``.
        issue: the ticket.
    """

    priority: int
    reference: str
    issue: shapes.Issue


def _page(github: ghapi.GitHub, path: str, number: int) -> Page:
    return issuelist.listed(
        ghapi.get(github, f"{path}&per_page={ghapi.PAGE_SIZE}&page={number}")
    )


def _stream(github: ghapi.GitHub, path: str, first: Page) -> Iterator[shapes.Issue]:
    # a page is raw items (the list holds PRs), so a full page may have more after it
    page, number = first, 1
    while True:
        yield from filter(None, page)
        if len(page) < ghapi.PAGE_SIZE:
            return
        number += 1
        page = _page(github, path, number)


def _tagged(slug: str, issues: Iterator[shapes.Issue]) -> Iterator[Tagged]:
    for each in issues:
        yield f"{slug}#{each.number}", each


def first_pages(
    github: ghapi.GitHub, repos: Sequence[config.Repo], name: str
) -> tuple[Sequence[str], Sequence[Page]]:
    """Read the first page of the tickets with a label, in every repository at once.

    Args:
        github: the API.
        repos: the repositories.
        name: the label.

    Returns:
        The path of each repository's list, and its first page.
    """
    query = f"issues?state=open&labels={name}&sort=created&direction=asc"
    paths = [f"repos/{each.slug}/{query}" for each in repos]
    return paths, concurrently.each(lambda path: _page(github, path, 1), paths)


def labelled(
    github: ghapi.GitHub, repos: Sequence[config.Repo], name: str
) -> Iterator[Tagged]:
    """The open tickets with a label, oldest first, across repositories.

    The first page of every repository is read at once; the others only when
    the merge reaches the end of the page before.

    Args:
        github: the API.
        repos: the repositories.
        name: the label.

    Returns:
        Each ticket's reference and the ticket, by creation time.
    """
    paths, firsts = first_pages(github, repos, name)
    streams = [
        _tagged(each.slug, _stream(github, path, first))
        for each, path, first in zip(repos, paths, firsts)
    ]
    return heapq.merge(*streams, key=lambda pair: pair[1].created_at)


def window(github: ghapi.GitHub, asked: Asked, count: int) -> Sequence[Found]:
    """The first ``count`` tickets of the order: by label, then oldest first.

    Args:
        github: the API.
        asked: which tickets are wanted.
        count: how many tickets to find.

    Returns:
        The tickets in order, fewer than ``count`` only when there are no more.
        A ticket with two labels is found under the first.
    """
    found: dict[str, Found] = {}
    for priority, name in enumerate(asked.labels):
        for each in _wanted(github, asked, priority, name):
            found.setdefault(each.reference, each)
            if len(found) >= count:
                return list(found.values())
    return list(found.values())


def _wanted(
    github: ghapi.GitHub, asked: Asked, priority: int, name: str
) -> Iterator[Found]:
    # the tickets of one label that no open PR works on
    for reference, issue in labelled(github, asked.repos, name):
        if reference not in asked.skip:
            yield Found(priority=priority, reference=reference, issue=issue)

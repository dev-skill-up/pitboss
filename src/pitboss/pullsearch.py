"""The open pull requests, read a page at a time (keyword: org-search).

The owner: "Next page of an org only while fewer than max(5, slots) lines are
printed." Each organisation has two searches of its open pull requests, oldest
first, of those that are not relock reviews and of those that are (GitHub's
``head:`` matches a branch prefix). The first page of each is read at once; a later page
of an organisation is read only when the walk reaches the end of the one before.
Every row read is kept in ``read``, so the listing of the world is what was read.
"""

import dataclasses
import heapq
from typing import Iterator, Mapping, Sequence

from . import concurrently, config, ghapi, listed, orgsearch

Repos = Mapping[str, config.Repo]  # the configured repositories by owner/name


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Paged:
    """One page of an organisation's search of open pull requests.

    Attributes:
        path: the search, to which the page is added.
        relock: whether it is the search of the relock reviews.
        rows: the rows of the configured repositories on the page.
        following: the number of the next page; 0 when this page is the last.
    """

    path: str
    relock: bool
    rows: Sequence[listed.Listed]
    following: int


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Pulls:
    """The open pull requests as the walk reads them.

    Attributes:
        pulls: those that are not relock reviews, oldest first, paged lazily.
        relocks: the relock reviews, oldest first, paged lazily.
        read: every row read so far (the first pages at once, then each page
            the streams reach), which the world's listing is.
    """

    pulls: Iterator[listed.Listed]
    relocks: Iterator[listed.Listed]
    read: Sequence[listed.Listed]


def _queries(prefix: str) -> Sequence[tuple[bool, Sequence[str]]]:
    # the open pull requests that are not relock reviews, and those that are
    if not prefix:
        return [(False, ["is:pr"])]
    return [(False, ["is:pr", f"-head:{prefix}"]), (True, ["is:pr", f"head:{prefix}"])]


def _page(
    github: ghapi.GitHub, asked: tuple[str, bool], number: int, repos: Repos
) -> Paged:
    path, relock = asked
    text = ghapi.get(github, f"{path}&per_page={ghapi.PAGE_SIZE}&page={number}")
    items = orgsearch.items(text)
    rows = [
        listed.searched_row(repo, relock, item)
        for item in items
        if (repo := orgsearch.repo_of(item, repos)) is not None
    ]
    following = number + 1 if len(items) == ghapi.PAGE_SIZE else 0
    return Paged(path=path, relock=relock, rows=rows, following=following)


def _stream(
    github: ghapi.GitHub, first: Paged, repos: Repos, read: list[listed.Listed]
) -> Iterator[listed.Listed]:
    # one organisation's rows: its first page, then a page each time it runs out
    page = first
    yield from page.rows
    while page.following:
        page = _page(github, (page.path, page.relock), page.following, repos)
        read.extend(page.rows)
        yield from page.rows


def ranked(settings: config.Config) -> Mapping[str, int]:
    """The place of each configured repository, which breaks a tie of age.

    Args:
        settings: the configuration.

    Returns:
        Each repository's index in the configuration, by ``owner/name``.
    """
    return {slug: at for at, slug in enumerate(orgsearch.configured(settings))}


def _asked(settings: config.Config) -> Sequence[tuple[str, bool]]:
    # each organisation's searches, and whether each is of the relock reviews
    return [
        (orgsearch.path(org, *terms), relock)
        for org in orgsearch.orgs(settings)
        for relock, terms in _queries(settings.lint.relock_prefix)
    ]


def opened(github: ghapi.GitHub, settings: config.Config) -> Pulls:
    """The open pull requests: the first page of each search read at once.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        The two streams, oldest first (a tie of age keeps the configuration's
        order of repositories), and the rows read so far.
    """
    repos = orgsearch.configured(settings)
    firsts = concurrently.each(
        lambda each: _page(github, each, 1, repos), _asked(settings)
    )
    read = [row for page in firsts for row in page.rows]
    plain = [page for page in firsts if not page.relock]
    relocks = [page for page in firsts if page.relock]
    return Pulls(
        pulls=_merged(github, plain, settings, read),
        relocks=_merged(github, relocks, settings, read),
        read=read,
    )


def _merged(
    github: ghapi.GitHub,
    firsts: Sequence[Paged],
    settings: config.Config,
    read: list[listed.Listed],
) -> Iterator[listed.Listed]:
    # the organisations' streams of one search, merged oldest first
    repos = orgsearch.configured(settings)
    rank = ranked(settings)
    streams = [_stream(github, page, repos, read) for page in firsts]
    return heapq.merge(*streams, key=lambda row: (row.created_at, rank[row.repo.slug]))

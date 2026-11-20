"""The open pull requests, one listing for each repository (keyword: pull-listing).

The owner: "Next page of an org only while fewer than max(5, slots) lines are
printed." Each configured repository has one listing of its open pull requests,
oldest first (``pulls?state=open&sort=created&direction=asc``), asked for all
repositories at once (plan 6.1: 33 listings for the quire configuration). Its
rows are split here into the pull requests that are not relock reviews and the
relock reviews (the head branch starts with the relock prefix). The first page
of each listing is read at once; a later page of a repository is read only when
the walk reaches the end of the one before. Every row read is kept in ``read``,
so the listing of the world is what was read.
"""

import dataclasses
import heapq
import json
from typing import Iterator, Mapping, Sequence

from . import concurrently, config, configrepos, ghapi, listed, orgsearch, totaljson


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Paged:
    """One page of a repository's open pull requests.

    Attributes:
        repo: the repository.
        rows: the rows on the page, plain and relock.
        following: the number of the next page; 0 when this page is the last.
    """

    repo: config.Repo
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


def _items(text: str) -> Sequence[Mapping[str, object]]:
    return [each for each in totaljson.records(json.loads(text)) if each]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class _Reader:
    # what reads a page of a repository's listing, once, and keeps what it read
    github: ghapi.GitHub
    prefix: str
    cache: dict[tuple[str, int], Paged] = dataclasses.field(default_factory=dict)
    read: list[listed.Listed] = dataclasses.field(default_factory=list)


def _page(reader: _Reader, repo: config.Repo, number: int) -> Paged:
    # a page both kinds of row reach is read once
    key = (repo.slug, number)
    if key not in reader.cache:
        path = f"{orgsearch.pulls_path(repo)}&per_page={ghapi.PAGE_SIZE}"
        items = _items(ghapi.get(reader.github, f"{path}&page={number}"))
        rows = [listed.listed_row(repo, reader.prefix, item) for item in items]
        following = number + 1 if len(items) == ghapi.PAGE_SIZE else 0
        reader.cache[key] = Paged(repo=repo, rows=rows, following=following)
        reader.read.extend(rows)
    return reader.cache[key]


def _stream(reader: _Reader, first: Paged, wanted: bool) -> Iterator[listed.Listed]:
    # one repository's rows of one kind: its first page, then a page each time it
    # runs out
    page = first
    while True:
        yield from (row for row in page.rows if row.relock == wanted)
        if not page.following:
            return
        page = _page(reader, page.repo, page.following)


def ranked(settings: config.Config) -> Mapping[str, int]:
    """The place of each configured repository, which breaks a tie of age.

    Args:
        settings: the configuration.

    Returns:
        Each repository's index in the configuration, by ``owner/name``.
    """
    return {slug: at for at, slug in enumerate(configrepos.slugs(settings))}


def opened(github: ghapi.GitHub, settings: config.Config) -> Pulls:
    """The open pull requests: the first page of each repository read at once.

    Args:
        github: the API.
        settings: the configuration.

    Returns:
        The two streams, oldest first (a tie of age keeps the configuration's
        order of repositories), and the rows read so far.
    """
    reader = _Reader(github=github, prefix=settings.lint.relock_prefix)
    firsts = concurrently.each(
        lambda repo: _page(reader, repo, 1), configrepos.repositories(settings)
    )
    reader.read[:] = [row for first in firsts for row in first.rows]  # in order
    rank = ranked(settings)

    def merged(wanted: bool) -> Iterator[listed.Listed]:
        streams = [_stream(reader, first, wanted) for first in firsts]
        return heapq.merge(
            *streams, key=lambda row: (row.created_at, rank[row.repo.slug])
        )

    return Pulls(pulls=merged(False), relocks=merged(True), read=reader.read)

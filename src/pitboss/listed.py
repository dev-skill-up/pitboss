"""One open pull request as the listing gives it, before any read of it (one-path).

The listing (``workorder.listing``) is complete and is what the order of work is
computed from; an item is read further only when the walk reaches it. Its rows
come from the organisations' searches (keyword: org-search), whose items carry no
branch and no head: those are known once the pull request is read.
"""

import dataclasses
from typing import AbstractSet, Mapping

from . import config, pullnames, relock
from .totaljson import text


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Listed:
    """One row of an open pull requests listing.

    Attributes:
        reference: its ``owner/name#number``.
        repo: its repository.
        number: its number.
        title: its title.
        branch: its head branch; empty when the search gave the row.
        head: its head commit; empty when the search gave the row.
        draft: whether it is a draft.
        created_at: when it was opened (ISO 8601), its place in the order.
        relock: whether its head branch starts with the relock prefix (the
            search ``head:<prefix>`` found it); its review ranks after every
            other item.
        works_on: the tickets it works on (``pullnames.names``, keyword: taken).
    """

    reference: str
    repo: config.Repo
    number: int
    title: str
    branch: str
    head: str
    draft: bool
    created_at: str
    relock: bool
    works_on: AbstractSet[str]


def listed_row(repo: config.Repo, prefix: str, row: Mapping[str, object]) -> Listed:
    """One open pull request as its listing row gives it.

    Args:
        repo: its repository.
        prefix: the relock branch prefix.
        row: the row of ``pulls?state=open``.

    Returns:
        The row.
    """
    head = row["head"] if isinstance(row["head"], dict) else {}
    branch = text(head.get("ref"))
    made = searched_row(repo, relock.is_relock(branch, prefix), row)
    names = pullnames.names(made.title, text(row.get("body")), branch, repo)
    sha = text(head.get("sha"))
    return dataclasses.replace(made, branch=branch, head=sha, works_on=names)


def searched_row(repo: config.Repo, relock: bool, item: Mapping[str, object]) -> Listed:
    """One open pull request as an organisation's search gives it (org-search).

    Args:
        repo: its repository.
        relock: whether the search of the relock prefix found it.
        item: the search's item.

    Returns:
        The row, with no branch and no head (the search has neither).
    """
    number = int(str(item["number"]))
    title, body = (text(item.get(key)) for key in ("title", "body"))
    return Listed(
        reference=f"{repo.slug}#{number}",
        repo=repo,
        number=number,
        title=title,
        branch="",
        head="",
        draft=bool(item.get("draft")),
        created_at=str(item["created_at"]),
        relock=relock,
        works_on=pullnames.names(title, body, "", repo),
    )

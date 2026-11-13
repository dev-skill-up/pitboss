"""One open pull request as the listing gives it, before any read of it (one-path).

The listing (``workorder.listing``) is complete and is what the order of work is
computed from; an item is read further only when the walk reaches it.
"""

import dataclasses
from typing import AbstractSet, Mapping

from . import config, pullnames, relock


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Listed:
    """One row of an open pull requests listing (``pulls?state=open``).

    Attributes:
        reference: its ``owner/name#number``.
        repo: its repository.
        number: its number.
        title: its title.
        body: its body.
        branch: its head branch.
        draft: whether it is a draft.
        created_at: when it was opened (ISO 8601), its place in the order.
        relock: whether its head branch starts with the relock prefix; its
            review ranks after every other item.
        works_on: the tickets it works on (``pullnames.names``, keyword: taken).
    """

    reference: str
    repo: config.Repo
    number: int
    title: str
    body: str
    branch: str
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
    number = int(str(row["number"]))
    head = row["head"]
    branch = str(head["ref"]) if isinstance(head, dict) else ""
    title, body = (str(row.get(key) or "") for key in ("title", "body"))
    return Listed(
        reference=f"{repo.slug}#{number}",
        repo=repo,
        number=number,
        title=title,
        body=body,
        branch=branch,
        draft=bool(row.get("draft")),
        created_at=str(row["created_at"]),
        relock=relock.is_relock(branch, prefix),
        works_on=pullnames.names(title, body, branch, repo),
    )

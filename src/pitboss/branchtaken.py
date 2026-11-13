"""A ticket a pull request names by its branch alone (keywords: taken, org-search).

The organisations' searches give no branch, so the tickets a branch names
(``pullnames.names``: ``fix-12`` works on ``#12``) are not in the listing's taken
set. A ticket the walk examines is checked here, with one read of its own
repository's open pull requests: a read for each examined ticket, never one for
each repository.
"""

import json
from typing import AbstractSet, Mapping, Sequence

from . import configrepos, ghapi, pullnames
from .totaljson import text


def _rows(body: str) -> Sequence[Mapping[str, object]]:
    found = json.loads(body)
    return [each for each in found if isinstance(each, dict)] if isinstance(found, list) else []


def named(github: ghapi.GitHub, reference: str) -> AbstractSet[str]:
    """The tickets the open pull requests of a ticket's repository name by branch.

    Args:
        github: the API.
        reference: the ticket, ``owner/name#number``.

    Returns:
        The tickets' references.
    """
    repo = configrepos.repo_of(reference)
    rows = ghapi.pages(github, f"repos/{repo.slug}/pulls?state=open", _rows)
    heads = [each.get("head") for each in rows]
    branches = [text(each.get("ref")) for each in heads if isinstance(each, dict)]
    return frozenset().union(
        *(pullnames.names("", "", branch, repo) for branch in branches)
    )

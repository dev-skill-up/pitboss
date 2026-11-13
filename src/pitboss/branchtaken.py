"""A ticket a pull request names by its branch alone (keywords: taken, org-search).

The organisations' searches give no branch, so the tickets a branch names
(``pullnames.names``: ``fix-12`` works on ``#12``) are not in the listing's taken
set. The open pull requests' branches of a repository are read here once a walk,
when the walk first examines a ticket of it (``readworld``); ``decide`` says which
tickets they name.
"""

import json
from typing import Mapping, Sequence

from . import ghapi
from .totaljson import text


def _rows(body: str) -> Sequence[Mapping[str, object]]:
    found = json.loads(body)
    return (
        [each for each in found if isinstance(each, dict)]
        if isinstance(found, list)
        else []
    )


def branches(github: ghapi.GitHub, slug: str) -> Sequence[str]:
    """The head branch of each open pull request of a repository.

    Args:
        github: the API.
        slug: the repository, ``owner/name``.

    Returns:
        The branches, as read (``decide`` says which ticket each names).
    """
    rows = ghapi.pages(github, f"repos/{slug}/pulls?state=open", _rows)
    heads = [each.get("head") for each in rows]
    return [text(each.get("ref")) for each in heads if isinstance(each, dict)]

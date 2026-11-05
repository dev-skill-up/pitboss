"""The files a PR changes, read only when asked (keyword: run-e2e, pitboss#199)."""

import json
from typing import Sequence

from . import ghapi


def file_names(text: str) -> Sequence[str]:
    """Parse a page of the files a pull request changes.

    Args:
        text: the response body of ``pulls/<number>/files``.

    Returns:
        The paths, each changed file's old path too when it was renamed.
    """
    items = json.loads(text)
    return [
        str(item[key])
        for item in items
        for key in ("filename", "previous_filename")
        if item.get(key)
    ]


def touches(
    github: ghapi.GitHub, slug: str, number: int, prefixes: Sequence[str]
) -> bool:
    """Whether a PR's diff touches a path that starts with one of the prefixes.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        number: the PR's number.
        prefixes: the path prefixes (those the e2e suite runs on).

    Returns:
        True when a changed file's path, or the old path of a renamed one,
        starts with one of them.
    """
    path = f"repos/{slug}/pulls/{number}/files"
    return any(
        name.startswith(tuple(prefixes))
        for name in ghapi.pages(github, path, file_names)
    )

"""The files a PR changes, read only when asked (keyword: run-e2e, pitboss#199)."""

import json
import re
from typing import Sequence

from . import ghapi

DEFINITION = re.compile(r"^([-+])[ \t]*(?:async[ \t]+)?def[ \t]+(test_\w+)", re.M)


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


def changed_tests(patches: str) -> Sequence[str]:
    """The test definitions a page of the files a pull request changes touches.

    Args:
        patches: the response body of ``pulls/<number>/files``.

    Returns:
        ``-test_name`` for each ``def test_name`` a patch removes and
        ``+test_name`` for each it adds.
    """
    items = json.loads(patches)
    return [
        sign + name
        for item in items
        for sign, name in DEFINITION.findall(item.get("patch", ""))
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

"""The issues and PRs the fake GitHub answers for ``slots set``."""

from typing import Mapping

PROJECT = "repos/owner/project"
LIBRARY = "repos/owner/lib"


def pull_issue(number: int) -> Mapping[str, object]:
    """The issue every PR is, as the API has it.

    Args:
        number: the PR's number.

    Returns:
        The issue's JSON.
    """
    return {
        "state": "open",
        "title": f"PR {number}",
        "pull_request": {},
        "body": "",
        "labels": [],
    }


ISSUES: Mapping[str, object] = {
    f"{PROJECT}/issues/9": {"state": "open", "title": "A ticket"},
    f"{PROJECT}/issues/50": {"state": "open", "title": "A ticket no list offers"},
    f"{PROJECT}/issues/3": {
        "state": "open",
        "pull_request": {},
        "body": "Fixes #9\n\nFixes #1\n",
    },
    f"{PROJECT}/issues/2": {
        "state": "open",
        "pull_request": {},
        "body": "no ticket named",
    },
    f"{LIBRARY}/issues/1": {"state": "open", "title": "A library ticket"},
    f"{LIBRARY}/issues/4": {
        "state": "open",
        "pull_request": {},
        "body": "Fixes owner/project#9",
    },
}

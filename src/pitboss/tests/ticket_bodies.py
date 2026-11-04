"""The issues and PRs the fake GitHub answers for ``slots set``."""

from typing import Mapping

PROJECT = "repos/owner/project"
LIBRARY = "repos/owner/lib"
ISSUES: Mapping[str, object] = {
    f"{PROJECT}/issues/9": {"title": "A ticket"},
    f"{PROJECT}/issues/50": {"title": "A ticket no list offers"},
    f"{PROJECT}/issues/3": {"pull_request": {}, "body": "Fixes #9\n\nFixes #1\n"},
    f"{PROJECT}/issues/2": {"pull_request": {}, "body": "no ticket named"},
    f"{LIBRARY}/issues/1": {"title": "A library ticket"},
    f"{LIBRARY}/issues/4": {"pull_request": {}, "body": "Fixes owner/project#9"},
}

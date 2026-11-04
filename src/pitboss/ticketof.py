"""The ticket a slot's task works on (keyword: slot-ticket)."""

import json
import re
import subprocess
from typing import Mapping

from . import config, fixes, ghapi, ledger

_FULL = re.compile(r"^(?P<owner>[\w.-]+)/(?P<name>[\w.-]+)#(?P<number>\d+)$")


def _unnamed(task: str, why: str) -> ledger.Refusal:
    return ledger.Refusal(reason=f"cannot name the ticket of {task}: {why}")


def _read(github: ghapi.GitHub, path: str) -> Mapping[str, object] | None:
    try:
        return dict(json.loads(ghapi.get(github, path)))
    except subprocess.CalledProcessError:
        return None


def resolve(github: ghapi.GitHub, task: str) -> str | ledger.Refusal:
    """Name the ticket of a task.

    A ticket is its own ticket; a PR's is the first ``Fixes`` line of its body.

    Args:
        github: the API.
        task: the task's id, as ``owner/name#number``.

    Returns:
        The ticket as ``owner/name#number``, or a refusal when the id is not a
        reference, cannot be read, or is a PR whose body has no ``Fixes`` line.
    """
    found = _FULL.match(task)
    if found is None:
        return _unnamed(repr(task), "it is not owner/name#number")
    repo = config.make_repo(found.group("owner"), found.group("name"))
    path = f"repos/{repo.slug}/issues/{found.group('number')}"
    item = _read(github, path)
    if item is None:
        return _unnamed(task, f"{path} cannot be read")
    if "pull_request" not in item:
        return task
    ticket = fixes.first_fixed(str(item.get("body") or ""), repo)
    return ticket or _unnamed(task, "its body has no Fixes line")

"""The inputs of a PR's gate that its own read holds no field for (keyword: gate).

``pulls`` reads a PR once: its object, its head's runs and statuses, its comments
and reviews. The gate needs more, read here once each: the repository's rules for
the base (required checks, the merge queue), its default branch, the files, the
tickets the body closes and the timeline; an open blocker is the decision's
(``examine``, plan 6.1).
A read GitHub answers with an error (a 404) is kept as ``{"_error": ...}`` so the
gate stops on it; a read that fails on every try ends the command (plan 3.2).
"""

import dataclasses
import json
import subprocess
from typing import Callable, Sequence

from . import config, ghapi, pullnames
from .actport import Pull
from .totaljson import members, records, text

Read = Callable[[str], object]


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Settings:
    """What the project says, not GitHub.

    Attributes:
        identity: the login the act verbs post with.
        authors: the logins whose PRs are the project's.
        max_lines: each repository's limit of changed lines.
    """

    identity: str
    authors: Sequence[str]
    max_lines: Callable[[str], int]


ALL = "all:"


def reader(github: ghapi.GitHub) -> Read:
    """Read one path, or the record of the failed read.

    A path that starts with ``all:`` is a list read through every page.

    Args:
        github: the API.

    Returns:
        The reader.
    """

    def read(path: str) -> object:
        try:
            if path.startswith(ALL):  # pages by number (keyword: proxy-paging)
                return ghapi.every(github, path.removeprefix(ALL))
            return json.loads(github.run(["gh", "api", path]).stdout)
        except subprocess.CalledProcessError as error:
            # GitHub's answer (a 404, a 422); a read that failed every try is
            # ``retrying.ReadFailed``, which ends the command (plan 3.2, P11)
            return {"_error": str(error)[:200]}

    return read


def _rules(read: Read, repo: str, branch: str) -> tuple[list[str], bool]:
    rules = records(read(f"repos/{repo}/rules/branches/{branch}"))
    checks = [
        text(each.get("context"))
        for rule in rules
        if rule.get("type") == "required_status_checks"
        for each in records(
            members(rule.get("parameters")).get("required_status_checks")
        )
    ]
    return checks, any(rule.get("type") == "merge_queue" for rule in rules)


def _states(read: Read, refs: Sequence[str]) -> dict[str, object]:
    found: dict[str, object] = {}
    for each in refs:
        where, _, number = each.rpartition("#")
        found[each] = read(f"repos/{where}/issues/{number}")
    return found


def _repo(slug: str) -> config.Repo:
    # the repository of an ``owner/name``
    return config.make_repo(*slug.split("/", 1))


def repo_reads(read: Read, repo: str, number: int, pull: tuple[str, str]) -> Pull:
    """What is read of a PR's repository and of the PR beyond its own read.

    Args:
        read: reads one path.
        repo: ``owner/name``.
        number: the PR's number.
        pull: its body and its base branch.

    Returns:
        The inputs, by the gate's names.
    """
    body, branch = pull
    checks, queue = _rules(read, repo, branch)
    tickets = sorted(pullnames.closed(body, _repo(repo)))
    return {
        "repo": repo,
        "number": number,
        "default_branch": text(members(read(f"repos/{repo}")).get("default_branch")),
        "required_checks": checks,
        "merge_queue": queue,
        "tickets": _states(read, tickets),
        "files": read(f"{ALL}repos/{repo}/pulls/{number}/files"),
        "holds": [],
    }


def said(settings: Settings, repo: str) -> Pull:
    """What the project says of a repository's gate, not GitHub.

    Args:
        settings: what the project says.
        repo: ``owner/name``.

    Returns:
        The inputs, by the gate's names.
    """
    return {
        "authors": set(settings.authors) | {settings.identity},
        "act_identity": settings.identity,
        "max_lines": settings.max_lines(repo),
    }


def timeline(read: Read, repo: str, number: int) -> object:
    """A PR's timeline, as GitHub answered.

    Args:
        read: reads one path.
        repo: ``owner/name``.
        number: the PR's number.

    Returns:
        Its events, or the record of the failed read.
    """
    return read(f"{ALL}repos/{repo}/issues/{number}/timeline")

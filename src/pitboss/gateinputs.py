"""The inputs of a PR's gate that its own read holds no field for (keyword: gate).

``pulls`` reads a PR once: its object, its head's runs and statuses, its comments
and reviews. The gate needs more, read here once each: the repository's rules for
the base (required checks, the merge queue), its default branch, the files, the
tickets the body closes, the items a ``Blocked-by:`` line names and the timeline.
A read that fails is kept as ``{"_error": ...}`` so the gate stops on it.
"""

import copy
import dataclasses
import json
from typing import Callable, Sequence

from . import blockedform, config, ghapi, pullnames
from .actport import Pull
from .totaljson import lines_of, members, records, text

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
        many = path.startswith(ALL)
        words = (
            ["--paginate", "--jq", ".[]", path.removeprefix(ALL)] if many else [path]
        )
        try:
            out = github.run(["gh", "api", *words]).stdout
            return lines_of(out) if many else json.loads(out)
        except (
            Exception
        ) as error:  # noqa: B902 - any failed read is the verdict's to stop on
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


def blockers_in(pull: Pull, inputs: Pull, repo: str) -> Pull:
    """A copy of a PR's inputs with each blocker its body names that they lack.

    Args:
        pull: the PR.
        inputs: its inputs; their ``blockers`` are the states read.
        repo: its repository, ``owner/name``.

    Returns:
        The copy; a blocker named and not read is "not read".
    """
    named = blockedform.named(text(pull.get("body")), repo)
    found = copy.deepcopy(dict(inputs))
    states = members(found.get("blockers"))
    found["blockers"] = {**dict.fromkeys(named, "not read"), **states}
    return found


def _repo(slug: str) -> config.Repo:
    # the repository of an ``owner/name``
    return config.make_repo(*slug.split("/", 1))


def _blockers(read: Read, body: str, repo: str) -> dict[str, object]:
    # keyword: blocked-by: the state of each item the one parse names
    found: dict[str, object] = {}
    for each in blockedform.named(body, repo):
        answer = _states(read, [each])[each]
        found[each] = text(members(answer).get("state")) or "not read"
    return found


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
        "files": read(f"{ALL}repos/{repo}/pulls/{number}/files?per_page=100"),
        "holds": [],
        "blockers": _blockers(read, body, repo),
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
    return read(f"{ALL}repos/{repo}/issues/{number}/timeline?per_page=100")

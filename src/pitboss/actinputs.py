"""The verdict's inputs for a live PR, read from GitHub (keyword: act-verbs, pitboss#444).

Every input the verdict requires (``totalverdict.REQUIRED``) is read here when a verb
asks: the repository's rules for its default branch (required checks, the merge
queue), the head's check runs and statuses, the files, the tickets the body closes,
the items a Blocked line or a block record names, and the timeline. A read that
fails is kept as ``{"_error": ...}`` so the verdict stops on it.
"""

import dataclasses
import json
import re
from typing import Callable, Mapping, Sequence

from . import ghapi, ticketreader, totalbody, totalreview
from .actcore import Inputs, Pull
from .totaljson import lines_of, mapping, name_at, records, text

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
    max_lines: Mapping[str, int]


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
            mapping(rule.get("parameters")).get("required_status_checks")
        )
    ]
    return checks, any(rule.get("type") == "merge_queue" for rule in rules)


def _refs(body: str, repo: str, pattern: re.Pattern[str], group: int) -> list[str]:
    found = []
    for match in pattern.finditer(body):
        ref = match.group(group)
        found.append(ref if not ref.startswith("#") else f"{repo}{ref}")
    return found


def _states(read: Read, refs: Sequence[str]) -> dict[str, object]:
    found: dict[str, object] = {}
    for ref in refs:
        where, _, number = ref.rpartition("#")
        answer = read(f"repos/{where}/issues/{number}")
        found[ref] = answer
    return found


def _blockers(
    read: Read, body: str, repo: str, timeline: Sequence[object], identity: str
) -> dict[str, object]:
    lines = [line for line in body.splitlines() if totalbody.BLOCKED.match(line)]
    named = [each for line in lines for each in totalbody.REFERENCE.findall(line)]
    named += [
        rest.split()[0]
        for _, rest in totalreview.act_records(
            records(timeline), identity, "blocked-by"
        )
        if rest.split()
    ]
    states = {}
    for ref in named:
        full = ref if not ref.startswith("#") else f"{repo}{ref}"
        state = _states(read, [full])[full]
        states[ref] = text(mapping(state).get("state")) or "not read"
    return states


def _head_reads(read: Read, repo: str, head: str) -> Pull:
    runs = mapping(read(f"repos/{repo}/commits/{head}/check-runs?per_page=100"))
    status = mapping(read(f"repos/{repo}/commits/{head}/status"))
    return {
        "check_runs": runs.get("check_runs", runs) if "_error" not in runs else runs,
        "statuses": (
            status.get("statuses", status) if "_error" not in status else status
        ),
    }


def inputs(read: Read, settings: Settings) -> Inputs:
    """The verdict's inputs of a PR, read live.

    Args:
        read: reads one path.
        settings: what the project says.

    Returns:
        What gives a PR's inputs.
    """

    def made(repo: str, number: int, pull: Pull, timeline: list[object]) -> Pull:
        body, branch = text(pull.get("body")), name_at(pull, "base", "ref")
        checks, queue = _rules(read, repo, branch)
        events = timeline or read(
            f"{ALL}repos/{repo}/issues/{number}/timeline?per_page=100"
        )
        tickets = _refs(body, repo, ticketreader.CLOSING, 2)
        return {
            "repo": repo,
            "number": number,
            "default_branch": text(
                mapping(read(f"repos/{repo}")).get("default_branch")
            ),
            "authors": set(settings.authors) | {settings.identity},
            "act_identity": settings.identity,
            "required_checks": checks,
            "merge_queue": queue,
            **_head_reads(read, repo, name_at(pull, "head", "sha")),
            "tickets": _states(read, tickets),
            "files": read(f"{ALL}repos/{repo}/pulls/{number}/files?per_page=100"),
            "max_lines": settings.max_lines.get(repo),
            "holds": [],
            "timeline": events,
            "blockers": _blockers(read, body, repo, records(events), settings.identity),
        }

    return made

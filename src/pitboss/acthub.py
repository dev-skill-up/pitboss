"""GitHub for the act verbs, through ``gh`` (keyword: act-verbs, pitboss#444).

Reads go through the reading runner and writes through the writing one, which is a
dry run unless the command was given ``--no-dry-run``. Each write kind of
``actcore.Change`` is one ``gh`` call, written in ``WRITES``.
"""

import dataclasses
import functools
import json
import urllib.parse
from typing import Callable, Mapping, Sequence

from . import ghapi
from .actport import Change, Hub, Pull
from .totaljson import lines_of, members, records, text

Words = Callable[[Change], Sequence[str]]
QUEUE = (
    "mutation($id: ID!) { dequeuePullRequest(input: {id: $id}) { clientMutationId } }"
)


def _api(method: str, path: str, *fields: str, jq: str = "") -> Sequence[str]:
    # the path is the last word, as every other write of pitboss puts it
    return ["gh", "api", "-X", method, *fields, *(["--jq", jq] if jq else []), path]


def _fields(change: Change, *names: str) -> Sequence[str]:
    found: list[str] = []
    for key in names:
        value = change.fields.get(key, "")
        if key == "labels":
            found.extend(f"labels[]={each}" for each in value.split(",") if each)
        elif value:
            found.append(f"{key}={value}")
    return [word for each in found for word in ("-f", each)]


def _issues(change: Change, rest: str = "") -> str:
    return f"repos/{change.repo}/issues{rest}"


def _issue_path(change: Change, rest: str = "") -> str:
    # the change's issue or PR, as an issue
    return _issues(change, f"/{change.number}{rest}")


def _comment(change: Change) -> str:
    # the comment the change names
    return _issues(change, f"/comments/{change.fields['id']}")


def _pulls(change: Change, rest: str = "") -> str:
    return f"repos/{change.repo}/pulls/{change.number}{rest}"


def _merge(*flags: str) -> Words:
    return lambda change: [
        "gh",
        "pr",
        "merge",
        str(change.number),
        "-R",
        change.repo,
        *flags,
    ]


def _branch_ref(change: Change) -> str:
    branch = urllib.parse.quote(change.fields["branch"], safe="/")
    return f"repos/{change.repo}/git/refs/heads/{branch}"


def _runs(change: Change, rest: str) -> str:
    return f"repos/{change.repo}/actions/runs/{change.fields['run']}/{rest}"


WRITES: Mapping[str, Words] = {
    "comment": lambda change: _api(
        "POST",
        _issue_path(change, "/comments"),
        *_fields(change, "body"),
        jq=".id",
    ),
    "comment-edit": lambda change: _api(
        "PATCH",
        _comment(change),
        *_fields(change, "body"),
    ),
    "comment-delete": lambda change: _api("DELETE", _comment(change)),
    "issue": lambda change: _api(
        "POST",
        _issues(change),
        *_fields(change, "title", "body", "labels"),
        jq=".number",
    ),
    "issue-edit": lambda change: _api(
        "PATCH", _issue_path(change), *_fields(change, "body")
    ),
    "close-issue": lambda change: _api(
        "PATCH",
        _issue_path(change),
        "-f",
        "state=closed",
        "-f",
        f"state_reason={change.fields['reason']}",
    ),
    "pr": lambda change: _api(
        "POST",
        f"repos/{change.repo}/pulls",
        *_fields(change, "head", "base", "title", "body"),
        jq=".number",
    ),
    "pr-edit": lambda change: _api(
        "PATCH", _pulls(change), *_fields(change, "title", "body")
    ),
    "pr-close": lambda change: _api("PATCH", _pulls(change), "-f", "state=closed"),
    "merge": lambda change: _api(
        "PUT", _pulls(change, "/merge"), "-f", "merge_method=merge"
    ),
    "arm": _merge("--auto", "--merge"),
    "disarm": _merge("--disable-auto"),
    "undraft": lambda change: [
        "gh",
        "pr",
        "ready",
        str(change.number),
        "-R",
        change.repo,
    ],
    "label": lambda change: _api(
        "POST",
        _issue_path(change, "/labels"),
        "-f",
        f"labels[]={change.fields['name']}",
    ),
    "unlabel": lambda change: _api(
        "DELETE",
        _issue_path(change, f"/labels/{urllib.parse.quote(change.fields['name'])}"),
    ),
    "dequeue": lambda change: [
        "gh",
        "api",
        "graphql",
        "-f",
        f"query={QUEUE}",
        "-f",
        f"id={change.fields['node_id']}",
    ],
    "update-branch": lambda change: _api("PUT", _pulls(change, "/update-branch")),
    "rerun": lambda change: _api("POST", _runs(change, "rerun-failed-jobs")),
    "cancel": lambda change: _api("POST", _runs(change, "cancel")),
    "dispatch": lambda change: _api(
        "POST",
        f"repos/{change.repo}/actions/workflows/{change.fields['workflow']}/dispatches",
        *_fields(change, "ref"),
    ),
    "branch-delete": lambda change: _api("DELETE", _branch_ref(change)),
}


def _one(github: ghapi.GitHub, path: str) -> object:
    return json.loads(ghapi.get(github, path) or "null")


def _every(github: ghapi.GitHub, path: str) -> Sequence[Pull]:
    out = github.run(["gh", "api", "--paginate", "--jq", ".[]", path]).stdout
    return [dict(each) for each in records(lines_of(out))]


def _one_pull(github: ghapi.GitHub, repo: str, number: int) -> Pull:
    found = _one(github, f"repos/{repo}/pulls/{number}")
    return found if isinstance(found, dict) else {}


def _timeline(github: ghapi.GitHub, repo: str, number: int) -> Sequence[object]:
    return _every(github, f"repos/{repo}/issues/{number}/timeline?per_page=100")


def _labeled(github: ghapi.GitHub, repo: str, label: str) -> Sequence[Pull]:
    quoted = urllib.parse.quote(label)
    return _every(
        github, f"repos/{repo}/issues?state=open&per_page=100&labels={quoted}"
    )


def _open_pulls(github: ghapi.GitHub, repo: str) -> Sequence[Pull]:
    return _every(github, f"repos/{repo}/pulls?state=open&per_page=100")


def _write(github: ghapi.GitHub, change: Change) -> str:
    # a dry run unless the command was asked for writes; a PR with no base goes
    # to the repository's default branch
    if change.kind == "pr" and not change.fields.get("base"):
        default = members(_one(github, f"repos/{change.repo}")).get("default_branch")
        fields = {**change.fields, "base": text(default) or "main"}
        change = dataclasses.replace(change, fields=fields)
    return github.mutate(list(WRITES[change.kind](change))).stdout.strip()


def hub_of(github: ghapi.GitHub) -> Hub:
    """GitHub through ``gh``.

    Args:
        github: the reading and the writing runner.

    Returns:
        The port.
    """
    return Hub(
        pull=functools.partial(_one_pull, github),
        timeline=functools.partial(_timeline, github),
        issues=functools.partial(_labeled, github),
        open_pulls=functools.partial(_open_pulls, github),
        write=functools.partial(_write, github),
    )

"""GitHub for the act verbs, through ``gh`` (keyword: act-verbs, pitboss#444).

Reads go through the reading runner and writes through the writing one, which is a
dry run unless the command was given ``--no-dry-run``. Each write kind of
``actcore.Change`` is one ``gh`` call, written in ``WRITES``.
"""

import dataclasses
import json
import urllib.parse
from typing import Callable, Mapping, Sequence

from . import ghapi
from .actcore import Change, Pull
from .totaljson import lines_of, mapping, records, text

Words = Callable[[Change], Sequence[str]]
QUEUE = (
    "mutation($id: ID!) { dequeuePullRequest(input: {id: $id}) { clientMutationId } }"
)


def _api(method: str, path: str, *fields: str, jq: str = "") -> Sequence[str]:
    # the path is the last word, as every other write of pitboss puts it
    return ["gh", "api", "-X", method, *fields, *(["--jq", jq] if jq else []), path]


def _fields(change: Change, *names: str) -> Sequence[str]:
    found = []
    for name in names:
        value = change.fields.get(name, "")
        if name == "labels":
            found.extend(f"labels[]={each}" for each in value.split(",") if each)
        elif value:
            found.append(f"{name}={value}")
    return [word for each in found for word in ("-f", each)]


def _issues(change: Change, rest: str = "") -> str:
    return f"repos/{change.repo}/issues{rest}"


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


def _runs(change: Change, rest: str) -> str:
    return f"repos/{change.repo}/actions/runs/{change.fields['run']}/{rest}"


WRITES: Mapping[str, Words] = {
    "comment": lambda change: _api(
        "POST",
        _issues(change, f"/{change.number}/comments"),
        *_fields(change, "body"),
        jq=".id",
    ),
    "comment-edit": lambda change: _api(
        "PATCH",
        _issues(change, f"/comments/{change.fields['id']}"),
        *_fields(change, "body"),
    ),
    "comment-delete": lambda change: _api(
        "DELETE", _issues(change, f"/comments/{change.fields['id']}")
    ),
    "issue": lambda change: _api(
        "POST",
        _issues(change),
        *_fields(change, "title", "body", "labels"),
        jq=".number",
    ),
    "issue-edit": lambda change: _api(
        "PATCH", _issues(change, f"/{change.number}"), *_fields(change, "body")
    ),
    "close-issue": lambda change: _api(
        "PATCH",
        _issues(change, f"/{change.number}"),
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
        _issues(change, f"/{change.number}/labels"),
        "-f",
        f"labels[]={change.fields['name']}",
    ),
    "unlabel": lambda change: _api(
        "DELETE",
        _issues(
            change,
            f"/{change.number}/labels/{urllib.parse.quote(change.fields['name'])}",
        ),
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
    "branch-delete": lambda change: _api(
        "DELETE",
        f"repos/{change.repo}/git/refs/heads/{urllib.parse.quote(change.fields['branch'], safe='/')}",
    ),
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GhHub:
    """GitHub through ``gh``.

    Attributes:
        github: the reading and the writing runner.
    """

    github: ghapi.GitHub

    def _get(self, path: str) -> object:
        return json.loads(self.github.run(["gh", "api", path]).stdout or "null")

    def _all(self, path: str) -> list[Pull]:
        out = self.github.run(["gh", "api", "--paginate", "--jq", ".[]", path]).stdout
        return [dict(each) for each in records(lines_of(out))]

    def pull(self, repo: str, number: int) -> Pull:
        """Read a PR.

        Args:
            repo: the repository.
            number: the PR.

        Returns:
            The PR as GitHub answers.
        """
        found = self._get(f"repos/{repo}/pulls/{number}")
        return found if isinstance(found, dict) else {}

    def timeline(self, repo: str, number: int) -> list[object]:
        """Read a PR's timeline.

        Args:
            repo: the repository.
            number: the PR.

        Returns:
            Its events, oldest first.
        """
        return list(self._all(f"repos/{repo}/issues/{number}/timeline?per_page=100"))

    def issues(self, repo: str, label: str) -> list[Pull]:
        """Read the open issues with a label.

        Args:
            repo: the repository.
            label: the label.

        Returns:
            The issues.
        """
        return self._all(
            f"repos/{repo}/issues?state=open&per_page=100&labels={urllib.parse.quote(label)}"
        )

    def pulls(self, repo: str) -> list[Pull]:
        """Read the open PRs.

        Args:
            repo: the repository.

        Returns:
            The PRs.
        """
        return self._all(f"repos/{repo}/pulls?state=open&per_page=100")

    def write(self, change: Change) -> str:
        """Make one write (a dry run unless the command was asked for writes).

        Args:
            change: the write.

        Returns:
            What GitHub answered: the number of what was made, when it was made.
        """
        if change.kind == "pr" and not change.fields.get("base"):
            branch = (
                text(mapping(self._get(f"repos/{change.repo}")).get("default_branch"))
                or "main"
            )
            change = dataclasses.replace(
                change, fields={**change.fields, "base": branch}
            )
        return self.github.mutate(list(WRITES[change.kind](change))).stdout.strip()

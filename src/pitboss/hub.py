"""The edge: GitHub over ``gh api`` (REST, every list paginated). The only I/O."""

import dataclasses
import subprocess
from collections.abc import Mapping, Sequence
from typing import Protocol

from . import actions
from . import jsonish as j


class Runner(Protocol):
    """Runs ``gh``."""

    def __call__(self, args: Sequence[str]) -> str:
        """Run ``gh`` with arguments.

        Args:
            args: the arguments after ``gh``.

        Returns:
            Standard output.
        """


def call_gh(args: Sequence[str]) -> str:
    """Run ``gh`` and return what it printed.

    Args:
        args: the arguments after ``gh``.

    Returns:
        Standard output.
    """
    done = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return done.stdout


def get(run: Runner, path: str) -> j.JsonValue:
    """Read one REST path, every page.

    Args:
        run: runs ``gh``.
        path: the path under the API root.

    Returns:
        The decoded JSON, the pages of a list joined.
    """
    pages = j.decode(run(["api", "--paginate", "--slurp", path]))
    first = j.obj(pages[0] if isinstance(pages, list) and pages else None)
    if isinstance(pages, list) and pages and isinstance(pages[0], list):
        return [item for page in pages if isinstance(page, list) for item in page]
    if "check_runs" in first and isinstance(pages, list):
        return [r for page in pages for r in j.rows(j.obj(page).get("check_runs"))]
    return first


ROUTES: Mapping[str, tuple[str, str, str]] = {
    "merge": ("PUT", "pulls/{n}/merge", "merge_method=merge"),
    "close": ("PATCH", "pulls/{n}", "state=closed"),
    "update-branch": ("PUT", "pulls/{n}/update-branch", ""),
    "comment": ("POST", "issues/{n}/comments", "body={text}"),
    "label": ("POST", "issues/{n}/labels", "labels[]={text}"),
    "review": ("POST", "issues/{n}/comments", "body={text}"),
    "plan-check": ("POST", "issues/{n}/comments", "body={text}"),
    "ruling": ("POST", "issues/{n}/comments", "body={text}"),
    "pr-create": ("POST", "pulls", "head={text}\nbase=main\ntitle={text}\ndraft=true"),
    "file-ticket": ("POST", "issues", "title={text}"),
}
READY = (
    "mutation($id:ID!){markPullRequestReadyForReview"
    "(input:{pullRequestId:$id}){clientMutationId}}"
)


def pull_field(call: Runner, repo: str, number: int, *path: str) -> str:
    """Read one string of a PR, by its path of keys.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        number: the PR.
        *path: the keys, outermost first.

    Returns:
        The string, empty when missing.
    """
    value = get(call, f"repos/{repo}/pulls/{number}")
    for key in path:
        value = j.obj(value).get(key)
    return j.text(value)


def send(call: Runner, repo: str, route: tuple[str, str, str]) -> None:
    """Write one REST call.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        route: the method, the path under the repository and a ``key=value`` field.
    """
    method, path, field = route
    base = ["api", "-X", method, f"repos/{repo}/{path}"]
    call([*base, *[x for f in field.splitlines() for x in ("-f", f)]])


def undraft(call: Runner, repo: str, ask: actions.Ask, number: int) -> None:
    """Mark a PR ready.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        ask: the verb.
        number: the PR.
    """
    node = pull_field(call, repo, number, "node_id")
    call(["api", "graphql", "-f", f"id={node}", "-f", f"query={READY}"])


def rerun(call: Runner, repo: str, ask: actions.Ask, number: int) -> None:
    """Run the failed jobs of the PR's head again.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        ask: the verb.
        number: the PR.
    """
    head = pull_field(call, repo, number, "head", "sha")
    found = j.obj(get(call, f"repos/{repo}/actions/runs?head_sha={head}"))
    for each in j.rows(found.get("workflow_runs")):
        if each.get("conclusion") == "failure":
            ident = j.count(each.get("id"))
            send(call, repo, ("POST", f"actions/runs/{ident}/rerun-failed-jobs", ""))


def dispatch(call: Runner, repo: str, ask: actions.Ask, number: int) -> None:
    """Start ``check.yml`` on the PR's branch.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        ask: the verb.
        number: the PR.
    """
    ref = pull_field(call, repo, number, "head", "ref")
    send(call, repo, ("POST", "actions/workflows/check.yml/dispatches", f"ref={ref}"))


def routed(call: Runner, repo: str, ask: actions.Ask, number: int) -> None:
    """Write a verb that is one REST call.

    Args:
        call: runs ``gh``.
        repo: ``owner/name``.
        ask: the verb and its text.
        number: the PR.
    """
    method, path, field = ROUTES[ask.verb]
    path = path.format(n=number)
    send(call, repo, (method, path, field.format(text=ask.text)))


ACTS = {
    "undraft": undraft,
    "rerun": rerun,
    "dispatch": dispatch,
    **{verb: routed for verb in ROUTES},
}


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Github:
    """The writes of ``actions.Hub`` for one repository."""

    _repo: str
    _run: Runner = call_gh

    def write(self, ask: actions.Ask, number: int) -> None:
        """Write one verb on one PR.

        Args:
            ask: the verb and its text.
            number: the PR.
        """
        ACTS[ask.verb](self._run, self._repo, ask, number)

"""Reading GitHub through ``gh api``, with the session's own auth and proxy."""

import dataclasses
import re
import subprocess
import urllib.parse
from typing import Callable, Iterable, Mapping, Sequence, TypeVar

from . import concurrently
from .running import Run

PAGE_SIZE = 100
_Item = TypeVar("_Item")


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class GitHub:
    """GitHub's REST API, through ``gh api``.

    Attributes:
        run: the runner reads go through.
        mutate: the runner changes go through (a dry run unless asked).
    """

    run: Run
    mutate: Run


def read_only(run: Run) -> GitHub:
    """The API for a command that only reads (it never changes GitHub).

    Args:
        run: the runner reads go through.

    Returns:
        The API, whose changes go through the same runner.
    """
    return GitHub(run=run, mutate=run)


def workflow_runs_path(slug: str, workflow: str) -> str:
    """The path of a workflow's runs.

    Args:
        slug: the repository's ``owner/name``.
        workflow: the workflow's file name or id.

    Returns:
        The path under ``https://api.github.com/``.
    """
    name = urllib.parse.quote(workflow, safe="")
    return f"repos/{slug}/actions/workflows/{name}/runs"


def get(github: GitHub, path: str) -> str:
    """Read one URL.

    Args:
        github: the API.
        path: the path under ``https://api.github.com/``.

    Returns:
        The response body.
    """
    return github.run(["gh", "api", path]).stdout


def post(github: GitHub, path: str) -> str:
    """Post to one URL (only when not a dry run).

    Args:
        github: the API.
        path: the path under ``https://api.github.com/``.

    Returns:
        The response body (empty in a dry run).
    """
    return github.mutate(["gh", "api", "-X", "POST", path]).stdout


def close_pull(github: GitHub, slug: str, number: int) -> str:
    """Close a pull request (only when not a dry run).

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        number: the pull request's number.

    Returns:
        The response body (empty in a dry run).
    """
    path = f"repos/{slug}/pulls/{number}"
    return github.mutate(
        ["gh", "api", "-X", "PATCH", "-f", "state=closed", path]
    ).stdout


def delete_branch(github: GitHub, slug: str, branch: str) -> str:
    """Delete a branch (only when not a dry run).

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        branch: the branch's name.

    Returns:
        The response body (empty in a dry run).
    """
    name = urllib.parse.quote(branch, safe="/")
    path = f"repos/{slug}/git/refs/heads/{name}"
    return github.mutate(["gh", "api", "-X", "DELETE", path]).stdout


def pages(
    github: GitHub,
    path: str,
    parse: Callable[[str], Sequence[_Item]],
    limit: int = 50,
) -> Sequence[_Item]:
    """Read a list page by page, until a short page or ``limit`` pages.

    Pages are asked for by number, because the ``Link`` headers GitHub
    returns name ``repositories/{id}`` URLs that some proxies refuse
    (proxy-paging).

    Args:
        github: the API.
        path: the list's path, with or without a query.
        parse: reads the items out of one page; for an array it gives an
            entry for each raw item, so that a short result is the last page.
        limit: the most pages read.

    Returns:
        Every item read.
    """
    separator = "&" if "?" in path else "?"
    found: list[_Item] = []
    for number in range(1, limit + 1):
        page = parse(
            get(github, f"{path}{separator}per_page={PAGE_SIZE}&page={number}")
        )
        found.extend(page)
        if len(page) < PAGE_SIZE:
            break
    return found


def pages_at_once(
    github: GitHub,
    path: str,
    parse: Callable[[str], Sequence[_Item]],
    limit: int,
) -> Sequence[_Item]:
    """Read a list of at most ``limit`` pages, the pages after the first together.

    The first page says whether there are more; a list known to be long is read
    in the time of two pages, not ``limit`` (keyword: pull-read, pitboss#453).

    Args:
        github: the API.
        path: the list's path, with or without a query.
        parse: reads the items out of one page, an entry for each raw item.
        limit: the most pages read.

    Returns:
        Every item read.
    """
    separator = "&" if "?" in path else "?"

    def page(number: int) -> Sequence[_Item]:
        return parse(
            get(github, f"{path}{separator}per_page={PAGE_SIZE}&page={number}")
        )

    first = page(1)
    if len(first) < PAGE_SIZE or limit < 2:
        return first
    rest = concurrently.each(page, range(2, limit + 1))
    return [*first, *(item for found in rest for item in found)]


def call_of(error: subprocess.CalledProcessError) -> str:
    """Name the API call that failed.

    Args:
        error: the failed ``gh api`` run.

    Returns:
        The last segment of its path, without the query (``check-runs``).
    """
    path = str(error.cmd[-1]).split("?", 1)[0]
    return path.rsplit("/", 1)[-1]


def status_of(error: subprocess.CalledProcessError) -> str:
    """Say how a ``gh api`` run failed.

    Args:
        error: the failed run.

    Returns:
        ``HTTP 500`` when ``gh`` printed a status, else ``gh exited N``.
    """
    found = re.search(r"HTTP \d{3}", str(error.stderr or ""))
    return found.group(0) if found else f"gh exited {error.returncode}"


def why(error: subprocess.CalledProcessError) -> str:
    """Say why a ``gh api`` run failed.

    Args:
        error: the failed run.

    Returns:
        The first line of ``gh``'s error, else ``gh exited N``.
    """
    lines = str(error.stderr or "").strip().splitlines()
    return lines[0] if lines else f"gh exited {error.returncode}"


def _why_unreadable(github: GitHub, slug: str) -> str:
    try:
        get(github, f"repos/{slug}")
    except subprocess.CalledProcessError as error:
        return why(error)
    return ""


def unreadable(github: GitHub, slugs: Iterable[str]) -> Mapping[str, str]:
    """Find the repositories this session cannot read.

    Args:
        github: the API.
        slugs: the repositories' ``owner/name``.

    Returns:
        Each unreadable repository, with the first line of ``gh``'s error.
    """
    wanted = sorted(set(slugs))
    reasons = concurrently.each(lambda slug: _why_unreadable(github, slug), wanted)
    return {slug: reason for slug, reason in zip(wanted, reasons) if reason}

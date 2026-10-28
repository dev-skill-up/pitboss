"""Reading GitHub through ``gh api``, with the session's own auth and proxy."""

import concurrent.futures
import dataclasses
import subprocess
import urllib.parse
from typing import Callable, Iterable, Mapping, Sequence, TypeVar

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
        parse: reads the items out of one page.
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


def _why_unreadable(github: GitHub, slug: str) -> str:
    try:
        get(github, f"repos/{slug}")
    except subprocess.CalledProcessError as error:
        lines = str(error.stderr or "").strip().splitlines()
        return lines[0] if lines else f"gh exited {error.returncode}"
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
    with concurrent.futures.ThreadPoolExecutor() as pool:
        reasons = pool.map(lambda slug: _why_unreadable(github, slug), wanted)
        return {slug: reason for slug, reason in zip(wanted, reasons) if reason}

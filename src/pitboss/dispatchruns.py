"""The dispatched runs of a head (keyword: run-e2e, pitboss#199)."""

import json
import subprocess
from typing import Callable, Sequence, TypeVar

from . import ghapi

CHECK_WORKFLOW = "check.yml"
_Item = TypeVar("_Item")
NOT_FOUND = "HTTP 404"


def run_ids(text: str) -> Sequence[int]:
    """Parse a page of workflow runs into their ids.

    Args:
        text: the response body of ``actions/runs``.

    Returns:
        The ids.
    """
    return [item["id"] for item in json.loads(text)["workflow_runs"]]


def run_times(text: str) -> Sequence[str]:
    """Parse a page of workflow runs into the times they were last updated.

    Args:
        text: the response body of ``actions/runs``.

    Returns:
        Each run's ``updated_at`` (when a completed run was last touched, so
        when it completed), empty for a run that gives none.
    """
    return [item.get("updated_at") or "" for item in json.loads(text)["workflow_runs"]]


def _dispatched(
    github: ghapi.GitHub,
    slug: str,
    head: str,
    parse: Callable[[str], Sequence[_Item]],
) -> Sequence[_Item]:
    # a repository with no check.yml answers 404: it has no dispatched run, and
    # that is an answer (keyword: no-check-workflow, pitboss#481)
    query = f"head_sha={head}&event=workflow_dispatch&status=completed"
    path = f"repos/{slug}/actions/workflows/{CHECK_WORKFLOW}/runs?{query}"
    try:
        return ghapi.pages(github, path, parse)
    except subprocess.CalledProcessError as refused:
        if ghapi.status_of(refused) != NOT_FOUND:
            raise
        return []


def completed_before(github: ghapi.GitHub, slug: str, head: str, when: str) -> bool:
    """Whether a dispatched run of the check workflow completed by a time.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        head: the head's SHA.
        when: the time (ISO 8601), a review's.

    Returns:
        True when a ``workflow_dispatch`` run of ``check.yml`` at the head had
        completed by then (a run that gives no time counts).
    """
    return any(each <= when for each in _dispatched(github, slug, head, run_times))


def completed(github: ghapi.GitHub, slug: str, head: str) -> bool:
    """Whether a run that a dispatch started has completed at a head.

    A draft's own run is not one: its CI skips the e2e jobs. A dispatched run
    of the check workflow runs them all.

    Args:
        github: the API.
        slug: the repository's ``owner/name``.
        head: the head's SHA.

    Returns:
        True when a ``workflow_dispatch`` run of ``check.yml`` at the head has
        completed (a dispatch of another workflow does not count).
    """
    return bool(_dispatched(github, slug, head, run_ids))

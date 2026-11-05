"""The dispatched runs of a head (keyword: run-e2e, pitboss#199)."""

import json
from typing import Sequence

from . import ghapi

CHECK_WORKFLOW = "check.yml"


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
    query = f"head_sha={head}&event=workflow_dispatch&status=completed"
    path = f"repos/{slug}/actions/workflows/{CHECK_WORKFLOW}/runs?{query}"
    return any(each <= when for each in ghapi.pages(github, path, run_times))


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
    query = f"head_sha={head}&event=workflow_dispatch&status=completed"
    path = f"repos/{slug}/actions/workflows/{CHECK_WORKFLOW}/runs?{query}"
    return bool(ghapi.pages(github, path, run_ids))

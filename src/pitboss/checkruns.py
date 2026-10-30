"""The check runs of a PR's head (keyword: check-runs)."""

from typing import Sequence

from . import shapes


def current_checks(
    checks: Sequence[shapes.CheckRun], head: str
) -> Sequence[shapes.CheckRun]:
    """Keep the latest run of each check name on the current head.

    A later run of the same check (a re-run, or a run that cancelled this
    one) supersedes it, and a run of an older head says nothing of this one.

    Args:
        checks: the check runs read.
        head: the PR's current head.

    Returns:
        The latest run of each name, in the order first seen.
    """
    latest: dict[str, shapes.CheckRun] = {}
    for run in checks:
        if run.head_sha not in ("", head):
            continue
        seen = latest.get(run.name)
        if seen is None or (run.started_at, run.id) > (seen.started_at, seen.id):
            latest[run.name] = run
    return list(latest.values())

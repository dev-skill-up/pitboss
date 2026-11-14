"""The check runs of a PR's head (keyword: check-runs)."""

from typing import Protocol, Sequence

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
    return latest([run for run in checks if run.head_sha in ("", head)])


class Started(Protocol):
    """What ``latest`` reads of a check run."""

    @property
    def id(self) -> int:
        """Return its id."""

    @property
    def name(self) -> str:
        """Return its name."""

    @property
    def started_at(self) -> str:
        """Return when it started."""


def latest[Run: Started](checks: Sequence[Run]) -> Sequence[Run]:
    """The latest run of each check name: the head's current runs.

    Args:
        checks: the check runs of one head.

    Returns:
        The latest run of each name, in the order first seen.
    """
    found: dict[str, Run] = {}
    for run in checks:
        seen = found.get(run.name)
        if seen is None or (run.started_at, run.id) > (seen.started_at, seen.id):
            found[run.name] = run
    return list(found.values())

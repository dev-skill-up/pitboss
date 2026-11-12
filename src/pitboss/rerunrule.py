"""When a re-run of a CI run is refused (keyword: rerun-rule, C13, pitboss#444).

Only a re-run to get rid of a flake is forbidden: a red check is root-caused
from its log. A re-run that works around a GitHub problem, as a run stuck queued
with no jobs, clears nothing a log could name, and is allowed.
"""

import dataclasses

QUEUED = "queued"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Run:
    """What GitHub says of a workflow run.

    Attributes:
        status: ``queued``, ``in_progress`` or ``completed``.
        jobs: how many jobs the run has.
    """

    status: str
    jobs: int


def stuck(run: Run) -> bool:
    """Whether GitHub left the run queued with no job to run.

    Args:
        run: the run.

    Returns:
        True for a queued run with no jobs.
    """
    return run.status == QUEUED and run.jobs == 0


def refusal(run: Run) -> str:
    """Why a re-run of the run is refused, empty when it is allowed.

    Args:
        run: the run to re-run.

    Returns:
        The reason, or an empty string for a run stuck on GitHub's side.
    """
    if stuck(run):
        return ""
    return "a re-run to get rid of a flake is refused: root-cause the log"

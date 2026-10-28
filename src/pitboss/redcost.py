"""The costs of a red run, computed from what GitHub says (nothing estimated)."""

import dataclasses
import enum
import statistics
from typing import Sequence

from . import redlog, redshapes, shapes
from .redtime import seconds

SUCCESS = "success"


class FixVerification(enum.Enum):
    """What the fix commit was verified by.

    Attributes:
        NO_FIX_PUSHED: no commit was pushed to the branch after the red head.
        MERGE_OF_MAIN: the commit after the red head is a merge (of main).
        NEVER_GREEN: a fix was pushed and no later run went green.
        ONE_GREEN_RUN: one later run after the fix went green.
        REPEATED_GREEN_RUNS: two or more later runs after the fix went green.
    """

    NO_FIX_PUSHED = "no fix was pushed"
    MERGE_OF_MAIN = "the next push was a merge of main"
    NEVER_GREEN = "a fix was pushed and no run after it went green"
    ONE_GREEN_RUN = "one green run after the fix"
    REPEATED_GREEN_RUNS = "a repeat: more than one green run after the fix"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class RunCost:
    """The cost line of one red run.

    Attributes:
        failed_seconds: seconds the run's failed jobs ran.
        extra_runs: full runs of the workflow on the branch after this one, up
            to and including the first green (all of them when none is).
        went_green: whether a later run on the branch went green.
        fix_push_seconds: seconds from the red to the fix push, if one.
        fix_to_green_seconds: seconds from the fix push to the green run's end.
        red_to_green_seconds: seconds from the red to the green run's end (the
            scheduling measure).
        detection_seconds: seconds CI took to show the failure (job start to
            the failing step's end).
        verification: what the fix was verified by.
    """

    failed_seconds: int
    extra_runs: int
    went_green: bool
    fix_push_seconds: int | None
    fix_to_green_seconds: int | None
    red_to_green_seconds: int | None
    detection_seconds: int
    verification: FixVerification


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Spread:
    """A distribution in seconds.

    Attributes:
        count: how many values.
        low: the smallest.
        median: the median.
        high: the largest.
    """

    count: int
    low: int
    median: int
    high: int


def _job_seconds(job: redshapes.Job) -> int:
    return seconds(job.started_at, job.completed_at) if job.completed_at else 0


def _red_at(facts: redshapes.RunFacts) -> str:
    return facts.run.updated_at


def _first_green(facts: redshapes.RunFacts) -> shapes.WindowRun | None:
    green = [run for run in facts.later if run.conclusion == SUCCESS]
    return green[0] if green else None


def _extra_runs(facts: redshapes.RunFacts, green: shapes.WindowRun | None) -> int:
    if green is None:
        return len(facts.later)
    return facts.later.index(green) + 1


def _detection(facts: redshapes.RunFacts) -> int:
    if facts.error is None:
        return sum(_job_seconds(job) for job in redlog.failed_jobs(facts.jobs)[:1])
    step = facts.error.step
    return seconds(facts.error.job.started_at, step.completed_at or step.started_at)


def verification(facts: redshapes.RunFacts) -> FixVerification:
    """Say what the fix commit was verified by.

    Args:
        facts: the red run's facts.

    Returns:
        The verification.
    """
    if facts.fix is None:
        return FixVerification.NO_FIX_PUSHED
    if facts.fix.merge:
        return FixVerification.MERGE_OF_MAIN
    after = [
        run
        for run in facts.later
        if run.created_at > facts.fix.date and run.conclusion == SUCCESS
    ]
    if not after:
        return FixVerification.NEVER_GREEN
    return (
        FixVerification.ONE_GREEN_RUN
        if len(after) == 1
        else FixVerification.REPEATED_GREEN_RUNS
    )


def run_cost(facts: redshapes.RunFacts) -> RunCost:
    """Compute the cost line of a red run.

    Args:
        facts: the red run's facts.

    Returns:
        The cost.
    """
    green = _first_green(facts)
    red = _red_at(facts)
    fix = facts.fix
    return RunCost(
        failed_seconds=sum(_job_seconds(job) for job in redlog.failed_jobs(facts.jobs)),
        extra_runs=_extra_runs(facts, green),
        went_green=green is not None,
        fix_push_seconds=seconds(red, fix.date) if fix else None,
        fix_to_green_seconds=(
            seconds(fix.date, green.updated_at) if fix and green else None
        ),
        red_to_green_seconds=seconds(red, green.updated_at) if green else None,
        detection_seconds=_detection(facts),
        verification=verification(facts),
    )


def distribution(values: Sequence[int]) -> Spread | None:
    """Summarize a distribution.

    Args:
        values: seconds.

    Returns:
        Its count, low, median and high, or ``None`` when empty.
    """
    if not values:
        return None
    return Spread(
        count=len(values),
        low=min(values),
        median=int(statistics.median(values)),
        high=max(values),
    )

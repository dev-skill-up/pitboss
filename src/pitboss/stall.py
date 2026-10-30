"""A relock PR whose check stays red: the sweep's STALL line (keyword: stall).

A relock PR (head branch starting ``relock/``) whose required check has been red
for over four hours, counted from the run's completion, is a stall: the next
relock fails on the same errors until the fix lands, so the skill's rules take
its fix before every other pull request but the merge of a ready one, unless
the PR also has RULING DUE or PAUSE (keyword: review-flow), when it waits for
the ruling or the owner first.
"""

import datetime
from typing import Mapping, Sequence

from . import pulls, shapes
from .markers import Marker

RELOCK_PREFIX = "relock/"
STALL_SECONDS = 4 * 3600
REQUIRED = "check"
NO_STEP = "no failed step read"


def _required(check: shapes.CheckRun) -> bool:
    return check.name == REQUIRED or check.name.endswith(f" / {REQUIRED}")


def red_seconds(pull: pulls.PullFacts, now: datetime.datetime) -> int | None:
    """How long a relock PR's required check has been red.

    Args:
        pull: the PR.
        now: the time now.

    Returns:
        The whole seconds since the completion of the longest-red required
        check run, or None for a PR that is not a relock PR or has no red
        required check run that completed.
    """
    if not pull.pull.head.branch.startswith(RELOCK_PREFIX):
        return None
    times = [
        datetime.datetime.fromisoformat(check.completed_at)
        for check in pulls.failed_checks(pull)
        if _required(check) and check.completed_at
    ]
    return int((now - min(times)).total_seconds()) if times else None


def _seconds_text(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    return f"{hours}h{rest // 60:02d}m{rest % 60:02d}s"


def _job_text(check: shapes.CheckRun, steps: Mapping[int, Sequence[str]]) -> str:
    names = ", ".join(steps.get(check.id) or ()) or NO_STEP
    return f"{check.name} (job {check.id}): {names}"


def lines(
    pull: pulls.PullFacts,
    now: datetime.datetime,
    steps: Mapping[int, Sequence[str]],
) -> Sequence[str]:
    """The STALL line of a relock PR red for over four hours, else nothing.

    Args:
        pull: the PR.
        now: the time now.
        steps: the names of the failed steps of each failed check (by id).

    Returns:
        The lines: one, or none (exactly four hours is not yet a stall).
    """
    red = red_seconds(pull, now)
    if red is None or red <= STALL_SECONDS:
        return []
    failing = pulls.failed_checks(pull)
    jobs = "; ".join(_job_text(check, steps) for check in failing)
    return [
        f"{Marker.STALL.text} {pulls.reference(pull)}: relock check red for"
        f" {_seconds_text(red)} ({red} seconds, over {STALL_SECONDS}); failing"
        f" steps: {jobs}; fix it before every other pull request but the merge"
        " of a ready one, unless it has RULING DUE or PAUSE (then it waits for"
        " the ruling or the owner)"
    ]

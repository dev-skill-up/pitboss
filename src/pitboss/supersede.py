"""A failed check run that a newer passing status answers (status-supersedes)."""

import dataclasses
from typing import Callable, Sequence

from . import shapes


def answers(
    check: shapes.CheckRun,
    status: shapes.CommitStatus,
    workflow_of: Callable[[int], str],
) -> bool:
    """Whether a status is the same check's later, passing answer.

    The status is the check's when its context is the check's name, or when
    the Actions run it points at and the check's run are the same workflow
    (a workflow's job ``lint`` posts the context ``text-lint``: the names
    differ, the workflow does not).

    Args:
        check: a failed check run.
        status: the newest status of one context of the head.
        workflow_of: the workflow file of a run id.

    Returns:
        True when the status succeeded after the check run completed and is
        the check's.
    """
    if not status.succeeded or status.created_at <= check.completed_at:
        return False
    if status.context == check.name:
        return True
    if not (status.run and check.run):
        return False
    return status.run == check.run or workflow_of(status.run) == workflow_of(check.run)


def settle(
    checks: Sequence[shapes.CheckRun],
    statuses: Sequence[shapes.CommitStatus],
    workflow_of: Callable[[int], str],
) -> Sequence[shapes.CheckRun]:
    """Clear the failure of each check run that a newer passing status answers.

    A failure stays when the check run is the newest of the two.

    Args:
        checks: the head's current check runs.
        statuses: the newest status of each context of the head.
        workflow_of: the workflow file of a run id.

    Returns:
        The check runs, a superseded failure no longer failed.
    """
    return [
        (
            dataclasses.replace(check, failed=False)
            if check.failed
            and any(answers(check, each, workflow_of) for each in statuses)
            else check
        )
        for check in checks
    ]

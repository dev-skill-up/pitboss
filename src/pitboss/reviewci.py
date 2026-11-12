"""An Execution review starts on a head whose runs all completed green (keyword: review-ci).

(Pitboss#444, case 38.) The brief says so; ``review-form --head SHA`` enforces it by
printing each run and its state and exiting 1 while one is not completed and
successful, so a reviewer cannot start on a head with a CI run in progress.
"""

from typing import Sequence

from . import shapes


def state(check: shapes.CheckRun) -> str:
    """What a run is in words.

    Args:
        check: the check run.

    Returns:
        ``success``, ``failed`` or ``not completed``.
    """
    if check.failed:
        return "failed"
    return "success" if check.succeeded else "not completed"


def lines(head: str, checks: Sequence[shapes.CheckRun]) -> Sequence[str]:
    """The lines that refuse a review of a head, none when every run is green.

    Args:
        head: the head's SHA.
        checks: the latest check runs of the head.

    Returns:
        A line for each run that is not a success, naming it and its state, and
        the refusal; none when every run completed with success.
    """
    waiting = [each for each in checks if not (each.finished and each.succeeded)]
    if not waiting:
        return []
    return [
        *[f"CI RUN {each.name} ({each.run}): {state(each)}" for each in waiting],
        f"refused: head {head} has {len(waiting)} run(s) not completed and"
        " successful; review starts when every run is green",
    ]

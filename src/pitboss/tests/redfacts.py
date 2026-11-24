"""A PR with one check, red or not, at FIX_CI (keyword: failure-text, #524)."""

import dataclasses

from .. import pulls, reviews, steps
from .blank import CHECK_RUN
from .test_report import facts


def red_pull(failed: bool = True, ended: str = "") -> pulls.PullFacts:
    """A PR at FIX_CI whose one check, ``canonical-files``, ended.

    Args:
        failed: whether the check failed.
        ended: when the check completed.

    Returns:
        The PR.
    """
    check = dataclasses.replace(
        CHECK_RUN,
        id=9,
        name="canonical-files",
        failed=failed,
        finished=True,
        completed_at=ended,
    )
    pull = facts(reviews.Standing.NONE, checks=[check])
    return dataclasses.replace(pull, step=steps.worker(steps.Task.FIX_CI))

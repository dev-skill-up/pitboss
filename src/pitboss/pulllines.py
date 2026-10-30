"""The action lines a PR gets before its checks are judged (keyword: pull-lines)."""

import datetime
from typing import Mapping, Sequence

from . import config, pulls, reviewline, roundline, stall, updateline


def lines(
    pull: pulls.PullFacts,
    now: datetime.datetime,
    settings: config.Config,
    steps: Mapping[int, Sequence[str]],
) -> Sequence[str]:
    """The STALL, UPDATE, RULING DUE or PAUSE and UNREADABLE REVIEW lines.

    Args:
        pull: the PR.
        now: the time now.
        settings: the configuration.
        steps: the failed steps of each failed check.

    Returns:
        The lines, in that order.
    """
    return (
        *stall.lines(pull, now, steps),
        *updateline.lines(pull, settings),
        *roundline.lines(pull),
        *reviewline.lines(pull),
    )

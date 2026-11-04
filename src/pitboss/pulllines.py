"""The action lines a PR gets before its checks are judged (keyword: pull-lines)."""

import datetime
from typing import Mapping, Sequence

from . import (
    analysisline,
    config,
    foldline,
    gateline,
    planeditline,
    pulls,
    reviewline,
    roundline,
    stall,
    updateline,
    work,
)
from .markers import Marker


def lines(
    pull: pulls.PullFacts,
    now: datetime.datetime,
    settings: config.Config,
    steps: Mapping[int, Sequence[str]],
) -> Sequence[str]:
    """The STALL, UPDATE, waiting-for-ruling, DRAFT ROUND and review-form lines.

    The waiting lines are RULING DUE, RULING UNREADABLE, RULING ESCALATES and PAUSE.
    The review-form lines are UNREADABLE REVIEW, RULING NO ANALYSIS and GATE PENDING.

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
        *planeditline.lines(pull),
        *_draft_lines(pull),
        *foldline.lines(pull),
        *reviewline.lines(pull),
        *analysisline.lines(pull),
        *gateline.lines(pull),
    )


def _draft_lines(pull: pulls.PullFacts) -> Sequence[str]:
    # keyword: draft-review (pitboss#156): a draft runs no CI, so its round is
    # said in the words `slots next` lists it with, before any ticket
    category = work.category_of(pull) if pull.pull.draft else None
    if category is None:
        return []
    return [
        f"{Marker.DRAFT_ROUND.text} {pulls.reference(pull)}:"
        f" {work.CATEGORY_WORDS[category]}; a draft has no check run, so it waits"
        " for none and is listed first in `slots next`, before every ticket"
    ]

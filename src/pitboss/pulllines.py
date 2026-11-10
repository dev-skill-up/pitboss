"""The action lines a PR gets before its checks are judged (keyword: pull-lines)."""

import datetime
from typing import Mapping, Sequence

from . import (
    analysisline,
    config,
    e2eline,
    fixedline,
    foldline,
    gateline,
    notesline,
    planeditline,
    planrowline,
    pulls,
    reviewline,
    roundline,
    stall,
    supersededline,
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
    """The STALL, UPDATE, FIXED ON BASE, waiting-for-ruling, DRAFT ROUND and form lines.

    The RUN E2E BEFORE APPROVAL line follows the DRAFT ROUND one.

    The waiting lines are RULING DUE, RULING UNREADABLE, RULING ESCALATES, PAUSE and
    PLAN EDITED.
    The review-form lines are PLAN ROW (a refusal of the body), UNREADABLE REVIEW,
    REVIEW NOTE, RULING NO ANALYSIS and GATE PENDING.

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
        *_branch_lines(pull, settings),
        *roundline.lines(pull),
        *planeditline.lines(pull),
        *_draft_lines(pull),
        *e2eline.lines(pull),
        *foldline.lines(pull),
        *_review_lines(pull),
        *gateline.lines(pull),
    )


def _branch_lines(pull: pulls.PullFacts, settings: config.Config) -> Sequence[str]:
    # the lines about the base: UPDATE where it is merged in, FIXED ON BASE where not
    return (
        *updateline.lines(pull, settings),
        *fixedline.lines(pull),
        *updateline.need_lines(pull, settings),
    )


def _review_lines(pull: pulls.PullFacts) -> Sequence[str]:
    return (
        *planrowline.lines(pull),
        *supersededline.lines(pull),
        *reviewline.lines(pull),
        *notesline.lines(pull),
        *analysisline.lines(pull),
    )


def _draft_lines(pull: pulls.PullFacts) -> Sequence[str]:
    # keyword: draft-review (pitboss#156): a draft's round is said as `slots next`
    # lists it, before a ticket
    category = work.category_of(pull) if pull.pull.draft else None
    if category is None:
        return []
    return [
        f"{Marker.DRAFT_ROUND.text} {pulls.reference(pull)}:"
        f" {work.CATEGORY_WORDS[category]}; it is"
        " listed first in `slots next`, before every ticket"
    ]

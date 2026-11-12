"""The action lines a PR gets before its checks are judged (keyword: pull-lines)."""

import datetime
from typing import Mapping, Sequence

from . import (
    analysisline,
    claimline,
    config,
    e2eline,
    fixedline,
    foldline,
    gateline,
    mechanical,
    knownred,
    notesline,
    planeditline,
    planrowline,
    pulls,
    shapes,
    steps,
    reviewline,
    roundline,
    stall,
    supersededline,
    updateline,
    work,
)
from .markers import Marker

# the lines that ask for runner time: the e2e dispatch, and a relock's re-dispatch
SPENDING = (steps.describe(steps.Next(step=steps.Step.RUN_E2E)),)


def lines(
    pull: pulls.PullFacts,
    now: datetime.datetime,
    settings: config.Config,
    steps: Mapping[int, Sequence[str]],
    failures: Mapping[int, shapes.Failure] = {},
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
        failures: what is known of each failed check, for MECHANICAL-FIX.

    Returns:
        The lines, in that order.
    """
    return knownred.gate(  # keyword: known-red (quire#1120)
        pull,
        (
            *stall.lines(pull, now, steps),
            *claimline.lines(pull),
            *_branch_lines(pull, settings, (now, failures)),
            *roundline.lines(pull),
            *planeditline.lines(pull),
            *_draft_lines(pull),
            *e2eline.lines(pull),
            *foldline.lines(pull),
            *_review_lines(pull),
            *gateline.lines(pull),
        ),
        SPENDING,
    )


def _branch_lines(
    pull: pulls.PullFacts,
    settings: config.Config,
    known: tuple[datetime.datetime, Mapping[int, shapes.Failure]],
) -> Sequence[str]:
    # the lines about the base: UPDATE where it is merged in, FIXED ON BASE where not;
    # a mechanical red (pitboss#32) replaces the plain fix line of the NEEDS
    fixes = mechanical.lines(pull, known[0], settings, known[1])
    needs = updateline.need_lines(pull, settings)
    kept = [each for each in needs if not (fixes and updateline.RED_FIX in each)]
    return (
        *updateline.lines(pull, settings),
        *fixedline.lines(pull),
        *kept,
        *fixes,
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

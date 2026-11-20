"""The step of a PR as read: the review flow's rows, with no I/O (keyword: review-flow).

The decider runs these rows (``decide.facts_of``); the reader runs them only to
choose which closures to read. A pins-check that printed OK takes the review's
place (keyword: pins-only), a review of a ruling's steps says why (keyword:
ruling-reason), and a step on failures the base answered says so (keyword:
fixed-on-base).
"""

import dataclasses
from typing import assert_never

from . import flow, pinsask, pullfacts, rulingreason, steps


def _step(read: pullfacts.PullRead) -> steps.Move:
    state, signals = read.state, read.signals
    step = pinsask.unreviewed(flow.next_step(state), signals.pins)
    match step:
        case steps.Idle():
            return step
        case steps.Next():
            ruled = rulingreason.times(state.comments, state.trusted, step)
            return dataclasses.replace(
                step, on_base=bool(signals.fixed), reason=rulingreason.reason(ruled)
            )
        case _:  # pragma: no cover
            assert_never(step)


def at_flow(read: pullfacts.PullRead) -> pullfacts.PullFacts:
    """A PR as read, at the step the review flow gives it.

    Args:
        read: the PR as read.

    Returns:
        Its facts, at that step.
    """
    return pullfacts.PullFacts(
        repo=read.repo,
        pull=read.pull,
        checks=read.checks,
        review=read.review,
        standing=read.standing,
        signals=read.signals,
        unreadable=read.unreadable,
        step=_step(read),
        review_rounds=read.review_rounds,
        relock=read.state.relock,
    )

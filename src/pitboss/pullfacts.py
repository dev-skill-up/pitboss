"""What one open pull request looks like now, with no I/O (keyword: one-path).

The decider's records hold these, so they live apart from the readers that fill
them (``pulls``, ``headchecks``): the decide, projection and render modules reach
no module that reads (P2).
"""

import dataclasses
from typing import Sequence

from . import (
    config,
    flowstate,
    headsignals,
    pullrecords,
    reviews,
    rounds,
    shapes,
    steps,
    straycomments,
)

HeadSignals = headsignals.HeadSignals


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullFacts:
    """What one open PR looks like now.

    Attributes:
        repo: its repository.
        pull: the PR.
        checks: the check runs of its head.
        review: its newest review that counts.
        standing: where its head stands with that review.
        signals: what may block it besides its checks (keyword: red-status).
        unreadable: its comments that try to be reviews and are not (keyword:
            unreadable-review).
        step: the one step the PR is at (keyword: review-flow).
        review_rounds: what its review rounds show.
        relock: whether its head branch starts with the relock prefix
            (keyword: relock).
    """

    repo: config.Repo
    pull: shapes.Pull
    checks: Sequence[shapes.CheckRun]
    review: reviews.Found | None
    standing: reviews.Standing
    signals: HeadSignals = dataclasses.field(default_factory=headsignals.HeadSignals)
    unreadable: straycomments.StrayComments = dataclasses.field(
        default_factory=straycomments.StrayComments
    )
    step: steps.Move
    review_rounds: rounds.Rounds = dataclasses.field(default_factory=rounds.Rounds)
    relock: bool = False


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class Posted:
    """What a PR's own read gives its gate, typed once (keyword: gate).

    Attributes:
        object: the PR object, as ``pullobject.pull_object`` types it.
        statuses: the newest commit status of each context of its head.
        sources: every comment and GitHub review of it, as read (the counted
            ones are a part of these).
    """

    object: pullrecords.PullObject
    statuses: Sequence[shapes.CommitStatus]
    sources: reviews.Sources


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class PullRead:
    """One open PR as read, before any step is decided (``decide.facts_of``).

    Attributes:
        repo: its repository.
        pull: the PR.
        checks: the check runs of its head.
        review: its newest review that counts.
        standing: where its head stands with that review.
        signals: what may block it besides its checks (keyword: red-status).
        unreadable: its comments that try to be reviews and are not (keyword:
            unreadable-review).
        review_rounds: what its review rounds show.
        state: what the review flow's rows ask of it (keyword: review-flow).
        posted: what its gate reads of it.
    """

    repo: config.Repo
    pull: shapes.Pull
    checks: Sequence[shapes.CheckRun]
    review: reviews.Found | None
    standing: reviews.Standing
    signals: HeadSignals
    unreadable: straycomments.StrayComments
    review_rounds: rounds.Rounds
    state: flowstate.PullState
    posted: Posted


# a PR as read: its facts, or why they could not be read
Read = PullFacts | shapes.Unreadable

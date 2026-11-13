"""What one open pull request looks like now, with no I/O (keyword: one-path).

The decider's records hold these, so they live apart from the readers that fill
them (``pulls``, ``headchecks``): the decide, projection and render modules reach
no module that reads (P2).
"""

import dataclasses
from typing import AbstractSet, Callable, Sequence

from . import basefix, config, pinsreading, reviews, rounds, shapes, steps, straycomments


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class HeadSignals:
    """What may block a PR besides its check runs (keyword: red-status, #162).

    Attributes:
        statuses: the commit statuses of its head that failed and that no later
            passing check run of the same name answers.
        labels: the names of the PR's labels.
        gate: why the review gate's status (``adversarial-review``) of a gated
            repository's head is not success, empty when it is, or the
            repository is not gated (keyword: review-gate, pitboss#166).
        rulings: the address and text of each Opus ruling comment of a trusted
            author, which a body with several tickets may cite (keyword: fold,
            pitboss#171).
        approved_plans: the digest of each Plan section a trusted review
            approved, which the Plan-row rule does not judge (keyword:
            plan-approved, pitboss#296).
        pins: what the pins-check command said of the PR, asked only at a
            review step (keyword: pins-only, pitboss#34).
        fixed: the base's later passing run of each failed check of the head,
            when it has one for every failed check, in a repository with a merge
            queue (keyword: fixed-on-base, pitboss#314).
        gone: the tests the PR's diff removes that its Execution says another
            replaced (keyword: superseded-pointer, pitboss#317).
        hold: says whether a runner-pressure hold covers its repository now
            (keyword: hold-scope, B20).
    """

    statuses: Sequence[shapes.CommitStatus] = ()
    labels: AbstractSet[str] = frozenset()
    gate: str = ""
    rulings: Sequence[tuple[str, str]] = ()
    approved_plans: Sequence[str] = ()
    pins: pinsreading.Reading = pinsreading.NOTHING
    fixed: Sequence[basefix.Answer] = ()
    gone: Sequence[str] = ()
    hold: Callable[[], bool] = lambda: False


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
    signals: HeadSignals = dataclasses.field(
        default_factory=HeadSignals
    )
    unreadable: straycomments.StrayComments = dataclasses.field(
        default_factory=straycomments.StrayComments
    )
    step: steps.Move
    review_rounds: rounds.Rounds = dataclasses.field(default_factory=rounds.Rounds)
    relock: bool = False

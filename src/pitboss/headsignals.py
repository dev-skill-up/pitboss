"""What may block a PR besides its check runs (keyword: red-status, #162).

Apart from ``pullfacts`` so that ``headchecks``, which makes it, does not sit on the
facts of a whole PR (keyword: one-path).
"""

import dataclasses
from typing import AbstractSet, Sequence

from . import basefix, pinsreading, shapes


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
        hold: whether a runner-pressure hold covers its repository now
            (keyword: hold-scope, B20).
    """

    statuses: Sequence[shapes.CommitStatus]
    labels: AbstractSet[str]
    gate: str
    rulings: Sequence[tuple[str, str]]
    approved_plans: Sequence[str]
    pins: pinsreading.Reading
    fixed: Sequence[basefix.Answer]
    hold: bool


# the signals of a head that has none
NONE = HeadSignals(
    statuses=(),
    labels=frozenset(),
    gate="",
    rulings=(),
    approved_plans=(),
    pins=pinsreading.NOTHING,
    fixed=(),
    hold=False,
)

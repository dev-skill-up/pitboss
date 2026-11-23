"""A PR's hand-backs as the review flow reads them (keyword: standing).

``hand-back-check`` records, in the project's main clone (and the worktree), each
head it accepted with the digest of the PR body and the ruling the PR had then. A
review is offered only for a head and body that were handed back (``standing``),
and a rejection counts as a round only when its head and body were
(``stagerounds``).
"""

import dataclasses
from typing import AbstractSet

ANY = "*"  # a record of an older version holds only the head: it covers any body
NO_RULING = "-"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class HandedBack:
    """What the worktrees of a PR's branch recorded.

    Attributes:
        required: whether a worker's hand-back is owed (every PR but a relock PR,
            whatever worktree exists: keyword durable-record, pitboss#513).
        states: each ``(head, body digest, ruling address)`` accepted, ``ANY`` where
            an older record did not hold it.
    """

    required: bool
    states: AbstractSet[tuple[str, str, str]]


NOT_REQUIRED = HandedBack(required=False, states=frozenset())


def _matches(kept: str, wanted: str) -> bool:
    return kept in (ANY, wanted)


def covers(handed: HandedBack, head: str, digest: str, ruling: str) -> bool:
    """Whether a head and body were handed back under a ruling.

    Args:
        handed: what was recorded.
        head: the PR's head.
        digest: the digest of the PR's body.
        ruling: the address of the PR's newest ruling, ``NO_RULING`` when none.

    Returns:
        True when no worker is required, or a record names the head, the body
        and the ruling.
    """
    return not handed.required or any(
        sha == head and _matches(body, digest) and _matches(ruled, ruling)
        for sha, body, ruled in handed.states
    )


def covers_state(handed: HandedBack, head: str, digest: str) -> bool:
    """Whether a head and body were handed back, under any ruling.

    Args:
        handed: what was recorded.
        head: a head, possibly abbreviated (a review's).
        digest: the digest of the body.

    Returns:
        True when no worker is required, or a record names the head (not an
        empty one, which is a prefix of every head) and the body.
    """
    named = bool(head) and any(
        sha.startswith(head) and _matches(body, digest)
        for sha, body, _ in handed.states
    )
    return not handed.required or named


def applied(handed: HandedBack, ruling: str) -> bool:
    """Whether a worker handed work back after a ruling.

    Args:
        handed: what was recorded.
        ruling: the address of the ruling.

    Returns:
        True when a record names the ruling (the worker saw it when it handed back).
    """
    return any(ruled == ruling for _, _, ruled in handed.states)

"""A PR's hand-backs, derived from what the PR shows (keyword: standing, #524).

A hand-back is not recorded anywhere a worker could write: it is what the PR's body
and comments say now. The body's last ``Head:`` line names the head and a trusted
clean ``Plan check`` is posted (the two things ``hand-back-check`` refuses without),
so a head is handed back exactly when ``derive`` says so, and nothing a worker could
forge by writing a file counts. A past review state counts when a clean check was
posted before the review (``covers_state``). ``handbackderive`` reads them.
"""

import dataclasses
from typing import Protocol, Sequence

NO_RULING = "-"


@dataclasses.dataclass(frozen=True, slots=True, kw_only=True)
class HandedBack:
    """What a PR shows of its worker's hand-backs.

    Attributes:
        required: whether a worker's hand-back is owed (every PR but a relock PR).
        head: the head the body's last ``Head:`` line names while the Plan check
            of the body's Plan is clean; empty when it is not.
        checked: when each clean ``Plan check`` of a trusted author was posted.
    """

    required: bool
    head: str
    checked: Sequence[str]


NOT_REQUIRED = HandedBack(required=False, head="", checked=())


def covers(handed: HandedBack, head: str) -> bool:
    """Whether a head was handed back.

    Args:
        handed: what the PR shows.
        head: the PR's head.

    Returns:
        True when no worker is required, or the body names the head under a clean
        Plan check.
    """
    return not handed.required or (bool(head) and handed.head == head)


def covers_state(handed: HandedBack, sha: str, when: str) -> bool:
    """Whether a reviewed state was handed back before its review.

    Args:
        handed: what the PR shows.
        sha: the reviewed head, possibly abbreviated.
        when: when the review was posted.

    Returns:
        True when no worker is required, or the review names a head and a clean
        Plan check was posted before it.
    """
    posted = any(each <= when for each in handed.checked)
    return not handed.required or (bool(sha) and posted)


class Reviewed(Protocol):
    """A review: the head it names and when it was posted."""

    @property
    def sha(self) -> str:
        """Return the head, possibly abbreviated."""

    @property
    def when(self) -> str:
        """Return when it was posted."""


def covers_review(handed: HandedBack, review: Reviewed) -> bool:
    """Whether a review's state was handed back before the review.

    Args:
        handed: what the PR shows.
        review: the review.

    Returns:
        What ``covers_state`` says of the review's head and time.
    """
    return covers_state(handed, review.sha, review.when)

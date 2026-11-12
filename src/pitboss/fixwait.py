"""A fix round that waits for its review (keyword: fix-round-waiting, pitboss#444 case 38).

On pitboss PRs 465 and 470 a worker did the fix round within minutes and the
re-review of it was never started, so the PRs sat for eleven hours. A PR whose
step is the review of a fix round (``work.fix_round``) that has waited more than
``MINUTES`` since its head's checks started, with no agent on it, is named first
in ``slots next`` with its head and the findings of the review it answers.
"""

import datetime
from typing import AbstractSet, Iterable, Sequence

from . import pulls, work

MINUTES = 30
PREFIX = "FIX ROUND WAITING"


def _when(text: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _since(facts: pulls.PullFacts) -> datetime.datetime | None:
    # the head's age: when its first check started (the push time is not read)
    started = [each.started_at for each in facts.checks if each.started_at]
    return min(map(_when, started)) if started else None


def lines(
    found: Iterable[pulls.PullFacts],
    now: datetime.datetime,
    held: AbstractSet[str],
) -> Sequence[str]:
    """The ``FIX ROUND WAITING`` lines of the PRs whose fix round has no reviewer.

    Args:
        found: the open PRs.
        now: the time now.
        held: the PRs an agent works on.

    Returns:
        A line for each PR at the review of a fix round for more than
        ``MINUTES``, the longest wait first, with the head, the findings' address
        and the command that prints the brief.
    """
    waiting = []
    for each in found:
        since = _since(each)
        reference = pulls.reference(each)
        if (
            since is None
            or reference in held
            or work.category_of(each) is not work.Category.REVIEW_FIX_ROUND
        ):
            continue
        minutes = int((now - since).total_seconds() // 60)
        if minutes > MINUTES:
            waiting.append((minutes, each))
    return [
        f"{PREFIX} {minutes} minutes: {pulls.reference(each)}, head"
        f" {each.pull.head.sha[:7]}, the findings it answers:"
        f" {each.review.url if each.review else ''}; review the fix round:"
        f" `pitboss slots next {pulls.reference(each)}`"
        for minutes, each in sorted(waiting, key=lambda pair: -pair[0])
    ]

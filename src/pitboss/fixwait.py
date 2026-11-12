"""A fix round that waits for its review (keyword: fix-round-waiting, case 38).

On pitboss PRs 465 and 470 a worker did the fix round within minutes and the
re-review of it was never started, so the PRs sat for eleven hours. A PR whose
step is the review of a fix round (``work.fix_round``) that has waited more than
``MINUTES`` since its head's checks started, with no agent on it, is named first
in ``slots next`` with its head and the findings of the review it answers.
"""

import datetime
from typing import AbstractSet, Iterable, Sequence

from . import pulls, stuckci, work

MINUTES = 30
PREFIX = "FIX ROUND WAITING"


def _since(facts: pulls.PullFacts) -> datetime.datetime | None:
    # the head's age: when its first check started (the push time is not read)
    started = [each.started_at for each in facts.checks if each.started_at]
    return min(map(stuckci.when, started)) if started else None


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
    waiting = [(_minutes(each, now, held), each) for each in found]
    return [
        _line(minutes, each)
        for minutes, each in sorted(waiting, key=lambda pair: -pair[0])
        if minutes > MINUTES
    ]


def _minutes(
    facts: pulls.PullFacts, now: datetime.datetime, held: AbstractSet[str]
) -> int:
    # how long the review of a fix round has waited; 0 for any other PR
    since = _since(facts)
    waiting = work.category_of(facts) is work.Category.REVIEW_FIX_ROUND
    if since is None or pulls.reference(facts) in held or not waiting:
        return 0
    return int((now - since).total_seconds() // 60)


def _line(minutes: int, facts: pulls.PullFacts) -> str:
    reference = pulls.reference(facts)
    return (
        f"{PREFIX} {minutes} minutes: {reference}, head {facts.pull.head.sha[:7]},"
        f" the findings it answers: {facts.review.url if facts.review else ''};"
        f" review the fix round: `pitboss slots next {reference}`"
    )

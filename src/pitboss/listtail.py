"""What follows the list of ``slots next``: the PR states, the alerts, the briefs.

The lines after the PR states: the duplicate PRs and the stuck runs (keywords:
duplicate-pr, stuck-ci), the disk and the override.
"""

import itertools
from typing import Iterable, Sequence

from . import diskwatch, duplicatepr, exempt, nextfound, pulls, stuckci


def lines(
    found: nextfound.Found,
    facts: Sequence[pulls.PullFacts],
    volume: diskwatch.Reading | None,
) -> Iterable[str]:
    """The lines that follow the list.

    Args:
        found: the context.
        facts: the PRs that were read.
        volume: the volume as read, None when unread.

    Returns:
        The lines, in order.
    """
    return itertools.chain(
        duplicatepr.lines(facts),
        stuckci.lines(found.github, facts, found.now),
        [diskwatch.line(volume)] if volume else [],
        [exempt.OVERRIDE],  # keyword: pitboss-exempt (pitboss#113)
    )

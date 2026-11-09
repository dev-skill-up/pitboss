"""The logs a FIX_CI brief names (keyword: red-cause, pitboss#420)."""

from typing import Sequence

from . import causeline, pulls


def of(found: pulls.PullFacts) -> Sequence[str]:
    """The log location of each failed check of a PR a worker fixes the CI of.

    Args:
        found: the PR, which is at the step that fixes its CI.

    Returns:
        ``<check name>: <url>`` for each failed check of its head.
    """
    failed = pulls.failed_checks(found)
    return [causeline.named_location(found.repo.slug, each) for each in failed]

"""The sweep's RULING NO ANALYSIS line (keyword: how-we-got-here)."""

from typing import Sequence

from . import analysis, pulls
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line for a PR whose newest Opus ruling has no analysis section.

    Args:
        pull: the PR.

    Returns:
        One line naming the comment, or none.
    """
    reference = pulls.reference(pull)
    return [
        f"{Marker.RULING_NO_ANALYSIS.text} {reference}: {url} has no"
        f" '{analysis.SECTION}' section: for each rejection before the ruling it"
        " names the finding, the rule or brief line that should have prevented"
        " it, and the prevention filed (a pitboss ticket number); ask an agent to"
        " add it (edit or repost the comment); the PR is not held for it"
        for url in pull.unreadable.unanalysed
    ]

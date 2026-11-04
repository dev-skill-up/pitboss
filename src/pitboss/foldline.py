"""The sweep's FOLDED PR line (keyword: fold, pitboss#171)."""

from typing import Sequence

from . import folds, pulls
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line for an open PR whose body closes several tickets with no ruling.

    Args:
        pull: the PR.

    Returns:
        One line, none when the body names one ticket or cites an Opus ruling
        comment (`Ruling: do these steps`) of the PR.
    """
    named = folds.folded(pull.pull.body, pull.signals.rulings)
    return [
        f"{Marker.FOLDED_PR.text} {pulls.reference(pull)}: its body closes"
        f" {len(named)} tickets ({', '.join(named)}) and cites no Opus ruling"
        " that allows it"
    ] * bool(named)

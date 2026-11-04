"""The sweep's GATE PENDING lines (keyword: review-gate, pitboss#166)."""

from typing import Sequence

from . import headchecks, pulls
from .markers import Marker


def lines(pull: pulls.PullFacts) -> Sequence[str]:
    """The line for a PR whose review gate is not success.

    Args:
        pull: the PR.

    Returns:
        One line, none when the repository is not gated or the gate passes.
    """
    if not pull.signals.gate:
        return []
    return [
        f"{Marker.GATE_PENDING.text} {pulls.reference(pull)}: {headchecks.GATE_CONTEXT}"
        f" {pull.signals.gate}: the repository cannot merge it; the review"
        " comment must be in the form of `pitboss review-form`"
    ]
